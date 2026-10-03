hc.ready(function() {
    var form = document.getElementById("login-tfa-form");

    function authenticate() {
        hc.hide("#pick-method");
        hc.show("#waiting");
        hc.hide("#error");

        var options = JSON.parse(document.getElementById("options").textContent);
        webauthnJSON.get(options).then(function(response) {
            document.getElementById("response").value = JSON.stringify(response);
            // Show the success message and save button
            hc.hide("#waiting");
            hc.show("#success");
            form.submit()
        }).catch(function(err) {
            // Show the error message
            hc.hide("#waiting");
            document.getElementById("error-text").textContent = err;
            hc.show("#error");
        });
    }

    hc.on("#use-key-btn", "click", authenticate);
    hc.on("#retry", "click", authenticate);

    // If we're not showing the TOTP option then start authentication on page load
    if (!hc.$("#pick-method")) {
        authenticate();
    }
});
