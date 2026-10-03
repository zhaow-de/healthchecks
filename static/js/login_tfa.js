hc.ready(function() {
    var form = document.getElementById("login-tfa-form");

    function showError(message) {
        hc.hide("#waiting");
        document.getElementById("error-text").textContent = message;
        hc.show("#error");
    }

    function authenticate() {
        hc.hide("#pick-method");
        hc.show("#waiting");
        hc.hide("#error");

        if (!window.PublicKeyCredential || !PublicKeyCredential.parseRequestOptionsFromJSON) {
            showError("This browser does not support security keys. Please use a current version of Chrome, Edge, Firefox or Safari.");
            return;
        }

        var options = JSON.parse(document.getElementById("options").textContent);
        var publicKey;
        try {
            publicKey = PublicKeyCredential.parseRequestOptionsFromJSON(options.publicKey);
        } catch (err) {
            showError(err);
            return;
        }

        navigator.credentials.get({publicKey: publicKey}).then(function(credential) {
            document.getElementById("response").value = JSON.stringify(credential.toJSON());
            // Show the success message and submit the form
            hc.hide("#waiting");
            hc.show("#success");
            form.submit();
        }).catch(showError);
    }

    hc.on("#use-key-btn", "click", authenticate);
    hc.on("#retry", "click", authenticate);

    // If we're not showing the TOTP option then start authentication on page load
    if (!hc.$("#pick-method")) {
        authenticate();
    }
});
