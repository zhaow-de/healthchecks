hc.ready(function () {
    var base = hc.base();
    var favicon = document.querySelector('link[rel="icon"]');

    // Schedule refresh to run every 3s when tab is visible and user
    // is active, every 60s otherwise
    var lastStatus = {};
    var lastStarted = {};
    function refreshStatus() {
        hc.getJSON(base + "?refresh=1", null, {timeout: 2000}).then(function(data) {
            var anyDown = false;
            for (var code in data) {
                var el = data[code];
                anyDown = anyDown || (el.status == "down");

                // Project codes are UUIDs and may start with a digit, which a CSS
                // "#id" selector rejects, so look the card up by id first.
                var card = document.getElementById(code);
                if (!card) continue;

                if (el.status != lastStatus[code]) {
                    hc.$$("div.status", card).forEach(function(div) {
                        div.className = "status ic-" + el.status;
                    });
                    lastStatus[code] = el.status;
                }

                if (el.started != lastStarted[code]) {
                    hc.$$("div.spinner", card).forEach(function(div) {
                        div.classList.toggle("started", el.started);
                    });
                    lastStarted[code] = el.started;
                }
            }
            var downPostfix = anyDown ? "_down" : "";
            favicon.href = `${base}/static/img/favicon${downPostfix}.svg`;
        }).catch(function() {});
    }

    adaptiveSetInterval(refreshStatus);
});
