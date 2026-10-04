hc.ready(function() {
    const form = document.getElementById("add-credential-form");

    function showError(message) {
        hc.hide("#waiting");
        document.getElementById("error-text").textContent = message;
        hc.show("#error");
    }

    function requestCredentials() {
        // Hide error & success messages, show the "waiting" message
        hc.hide("#name-next");
        hc.show("#waiting");
        hc.hide("#error");
        hc.hide("#success");

        if (!window.PublicKeyCredential || !PublicKeyCredential.parseCreationOptionsFromJSON) {
            showError("This browser does not support security keys. Please use a current version of Chrome, Edge, Firefox or Safari.");
            return;
        }

        const options = JSON.parse(document.getElementById("options").textContent);
        let publicKey;
        try {
            publicKey = PublicKeyCredential.parseCreationOptionsFromJSON(options.publicKey);
        } catch (err) {
            showError(err);
            return;
        }

        navigator.credentials.create({publicKey: publicKey}).then(function(credential) {
            document.getElementById("response").value = JSON.stringify(credential.toJSON());
            // Show the success message and save button
            hc.hide("#waiting");
            hc.show("#success");
        }).catch(showError);
    }

    hc.on("#name", "keypress", function(e) {
        if (e.key === "Enter") {
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
