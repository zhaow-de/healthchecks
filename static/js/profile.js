hc.ready(function() {
    var tzTom = new TomSelect("select[name=tz]", {
        diacritics: false,
        maxOptions: null,
        placeholder: "Type to search",
        plugins: ["dropdown_input", "no_backspace_delete"],
        refreshThrottle: 0,
    });

    hc.on(".leave-project", "click", function() {
        hc.$("#leave-project-name").textContent = this.dataset.name;
        hc.$("#leave-project-code").value = this.dataset.code;
        hc.showModal("#leave-project-modal");
        return false;
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
