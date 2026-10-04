hc.ready(function () {
    // Event handler for input's oninput event
    const validateAndSubmit = function () {
        if (this.validity.valid) {
            // Use requestSubmit() instead of submit() because submit()
            // does not generate the onsubmit event.
            this.form.requestSubmit();
        }
    };

    // Event handler for form's onsubmit event
    const checkDoubleSubmit = function (e) {
        if (this.dataset.submitted) {
            e.preventDefault();
        }

        this.dataset.submitted = true;
    };

    // Hook up validateAndSubmit to all input elements with the
    // "data-auto-submit" attribute
    document.querySelectorAll("input[data-auto-submit]").forEach((input) => {
        input.addEventListener("input", validateAndSubmit);
        input.form.addEventListener("submit", checkDoubleSubmit);
    });
});
