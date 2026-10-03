hc.ready(function() {
    function updatePreview() {
        hc.post(window.location.href, hc.serialize("#badge-settings-form")).then(function(r) {
            return r.text();
        }).then(function(data) {
            document.getElementById("preview").innerHTML = data;
            hc.$$(".fetch-json").forEach(function(el) {
                hc.getJSON(el.dataset.url).then(function(data) {
                    el.innerText = JSON.stringify(data);
                });
            });
        });
    }

    // The radios and selects are all inside the form, and change bubbles.
    hc.on("#badge-settings-form", "change", updatePreview);
});
