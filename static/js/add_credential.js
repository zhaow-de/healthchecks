hc.ready(function() {
    var form = document.getElementById("add-credential-form");

    function requestCredentials() {
        // Hide error & success messages, show the "waiting" message
        hc.hide("#name-next");
        hc.show("#waiting");
        hc.hide("#error");
        hc.hide("#success");

        var options = JSON.parse(document.getElementById("options").textContent);
        // Override pubKeyCredParams prepared by python-fido2,
        // to only list ES256 (-7) and RS256 (-257), **and omit Ed25519 (-8)**.
        // This is to work around a bug in Firefox < 119. Affected
        // Firefox versions serialize Ed25519 keys incorrectly,
        // the workaround is to exclude Ed25519 from pubKeyCredParams.
        //
        // For reference, different project, similar issue:
        // https://github.com/MasterKale/SimpleWebAuthn/issues/463
        options.publicKey.pubKeyCredParams= [
            {"alg": -7, "type": "public-key"},
            {"alg": -257, "type": "public-key"}
        ]

        webauthnJSON.create(options).then(function(response) {
            document.getElementById("response").value = JSON.stringify(response);
            // Show the success message and save button
            hc.hide("#waiting");
            hc.show("#success");
        }).catch(function(err) {
            // Show the error message
            hc.hide("#waiting");
            document.getElementById("error-text").textContent = err;
            hc.show("#error");
        });
    }

    hc.on("#name", "keypress", function(e) {
        if (e.key == "Enter") {
            e.preventDefault();
            requestCredentials();
        }
    });

    hc.on("#name-next", "click", requestCredentials);
    hc.on("#retry", "click", requestCredentials);

    // Disable the submit button to prevent double submission
    form.addEventListener("submit", function() {
        document.getElementById("add-credential-submit").disabled = true;
    });

});
