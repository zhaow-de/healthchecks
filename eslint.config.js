// CommonJS, because pre-commit installs `globals` into its own Node environment, which require() finds
// through NODE_PATH and an ES import does not.
const globals = require("globals");

module.exports = [
    {
        languageOptions: {
            ecmaVersion: "latest",
            // Classic scripts under {% compress js %}: one global scope per page.
            sourceType: "script",
            globals: {
                ...globals.browser,
                // static/vendor
                bootstrap: "readonly",
                noUiSlider: "readonly",
                TomSelect: "readonly",
                // Defined by one page script and used by others; a page loads the defining
                // script first.
                hc: "readonly",
                adaptiveSetInterval: "readonly",
                DateFormatter: "readonly",
                loadPingDetails: "readonly",
                makeSlider: "readonly",
                bindDuration: "readonly",
                schedulePreview: "readonly",
            },
        },
        rules: {
            "no-undef": "error",
            "no-unused-vars": "error",
        },
    },
];
