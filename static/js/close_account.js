hc.ready(function() {
    // Disable the button to prevent double submission
    document.forms.close_account.addEventListener("submit", function() {
        document.getElementById("close-go").disabled = true;
    });
});
