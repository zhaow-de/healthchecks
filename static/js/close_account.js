window.addEventListener("DOMContentLoaded", function() {
    const submitBtn = document.getElementById("close-go");
    submitBtn.addEventListener("click", function() {
        if (!submitBtn.disabled) {
            submitBtn.disabled = true;
            document.forms.close_account.submit();
        }
    });
});
