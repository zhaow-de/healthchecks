import json
from hashlib import sha256

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.test import SimpleTestCase
from fido2.cose import ES256
from fido2.utils import websafe_encode
from fido2.webauthn import (
    AttestationObject,
    AttestedCredentialData,
    AuthenticationResponse,
    AuthenticatorAssertionResponse,
    AuthenticatorAttestationResponse,
    AuthenticatorData,
    CollectedClientData,
    RegistrationResponse,
)

from hc.lib.webauthn import CreateHelper, GetHelper

RP_ID = "example.org"
ORIGIN = "https://example.org"
CREDENTIAL_ID = b"\x01" * 16


class SoftwareAuthenticator:
    """A security key emulated in software, with a "none" attestation."""

    def __init__(self) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.rp_id_hash = sha256(RP_ID.encode()).digest()

    def register(self, challenge: str) -> str:
        client_data = CollectedClientData.create("webauthn.create", challenge, ORIGIN)
        public_key = ES256.from_cryptography_key(self.key.public_key())
        credential = AttestedCredentialData.create(b"\x00" * 16, CREDENTIAL_ID, public_key)
        flags = AuthenticatorData.FLAG.UP | AuthenticatorData.FLAG.AT
        auth_data = AuthenticatorData.create(self.rp_id_hash, flags, 0, credential)
        response = RegistrationResponse(
            raw_id=CREDENTIAL_ID,
            response=AuthenticatorAttestationResponse(
                client_data=client_data,
                attestation_object=AttestationObject.create("none", auth_data, {}),
            ),
        )
        return json.dumps(dict(response))

    def sign(self, challenge: str, key: ec.EllipticCurvePrivateKey | None = None) -> str:
        client_data = CollectedClientData.create("webauthn.get", challenge, ORIGIN)
        auth_data = AuthenticatorData.create(self.rp_id_hash, AuthenticatorData.FLAG.UP, 1)
        signer = key or self.key
        signature = signer.sign(bytes(auth_data) + client_data.hash, ec.ECDSA(hashes.SHA256()))
        response = AuthenticationResponse(
            raw_id=CREDENTIAL_ID,
            response=AuthenticatorAssertionResponse(
                client_data=client_data,
                authenticator_data=auth_data,
                signature=signature,
            ),
        )
        return json.dumps(dict(response))


class WebAuthnTestCase(SimpleTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.authenticator = SoftwareAuthenticator()

    def _register(self) -> bytes:
        helper = CreateHelper(RP_ID, [])
        options, state = helper.prepare("alice@example.org")
        response_json = self.authenticator.register(options["publicKey"]["challenge"])
        credential = helper.verify(state, response_json)
        assert credential is not None
        return credential

    def test_create_helper_returns_credential_data(self) -> None:
        credential = AttestedCredentialData(self._register())

        self.assertEqual(credential.credential_id, CREDENTIAL_ID)
        expected_key = ES256.from_cryptography_key(self.authenticator.key.public_key())
        self.assertEqual(credential.public_key, expected_key)

    def test_create_helper_ignores_the_level3_fields_of_to_json(self) -> None:
        # The browser posts credential.toJSON(), whose response also carries the public key
        # and authenticator data; the stored credential must come from the attestationObject alone.
        helper = CreateHelper(RP_ID, [])
        options, state = helper.prepare("alice@example.org")
        doc = json.loads(self.authenticator.register(options["publicKey"]["challenge"]))

        other_key = ec.generate_private_key(ec.SECP256R1()).public_key()
        spki = other_key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        other_credential = AttestedCredentialData.create(b"\x00" * 16, b"\x02" * 16, ES256.from_cryptography_key(other_key))
        other_auth_data = AuthenticatorData.create(sha256(RP_ID.encode()).digest(), 0x41, 0, other_credential)
        doc["response"]["publicKey"] = websafe_encode(spki)
        doc["response"]["publicKeyAlgorithm"] = -7
        doc["response"]["authenticatorData"] = websafe_encode(bytes(other_auth_data))
        doc["response"]["transports"] = ["usb"]
        doc["authenticatorAttachment"] = "cross-platform"
        doc["clientExtensionResults"] = {}

        blob = helper.verify(state, json.dumps(doc))
        assert blob is not None
        credential = AttestedCredentialData(blob)
        self.assertEqual(credential.credential_id, CREDENTIAL_ID)
        expected_key = ES256.from_cryptography_key(self.authenticator.key.public_key())
        self.assertEqual(credential.public_key, expected_key)

    def test_create_helper_rejects_wrong_challenge(self) -> None:
        helper = CreateHelper(RP_ID, [])
        _, state = helper.prepare("alice@example.org")
        response_json = self.authenticator.register("not-the-issued-challenge")

        with self.assertRaisesMessage(ValueError, "Wrong challenge in response."):
            helper.verify(state, response_json)

    def test_get_helper_accepts_valid_signature(self) -> None:
        helper = GetHelper(RP_ID, [self._register()])
        options, state = helper.prepare()

        response_json = self.authenticator.sign(options["publicKey"]["challenge"])
        self.assertTrue(helper.verify(state, response_json))

    def test_get_helper_rejects_signature_by_other_key(self) -> None:
        helper = GetHelper(RP_ID, [self._register()])
        options, state = helper.prepare()

        other_key = ec.generate_private_key(ec.SECP256R1())
        response_json = self.authenticator.sign(options["publicKey"]["challenge"], key=other_key)
        self.assertFalse(helper.verify(state, response_json))
