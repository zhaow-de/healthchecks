hc.ready(function() {
    const tzTom = new TomSelect("select[name=tz]", {
        diacritics: false,
        maxOptions: null,
        placeholder: "Type to search",
        plugins: ["dropdown_input", "no_backspace_delete"],
        refreshThrottle: 0,
    });

    const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (document.getElementById("tz").value !== browserTz) {
        hc.$("#browser-tz-hint b").textContent = browserTz;
        hc.show("#browser-tz-hint");
    }
    hc.on("#browser-tz-hint a", "click", function() {
        tzTom.setValue(browserTz, true);
        return false;
    });

});
