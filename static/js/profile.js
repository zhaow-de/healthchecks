hc.ready(function() {
    var tzTom = new TomSelect("select[name=tz]", {
        diacritics: false,
        maxOptions: null,
        placeholder: "Type to search",
        plugins: ["dropdown_input", "no_backspace_delete"],
        refreshThrottle: 0,
    });

    var browserTz = null;
    try {
        browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch(err) {};

    if (browserTz && document.getElementById("tz").value != browserTz) {
        hc.$("#browser-tz-hint b").textContent = browserTz;
        hc.show("#browser-tz-hint");
    }
    hc.on("#browser-tz-hint a", "click", function() {
        tzTom.setValue(browserTz, true);
        return false;
    });

});
