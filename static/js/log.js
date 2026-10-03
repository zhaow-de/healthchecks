hc.ready(function () {
    // The AbortController of the request in flight, or null
    var activeRequest = null;
    var slider = document.getElementById("end");

    // Look up the active tz switch to determine the initial display timezone:
    var activeTz = hc.$("#tz-switcher .active");
    var dateFormatter = new DateFormatter(activeTz ? activeTz.dataset.tz : undefined);

    function updateSliderPreview() {
        var toFormatted = "now, live updates";
        if (slider.value != slider.max) {
            var dt = new Date(slider.value * 1000);
            toFormatted = dateFormatter.formatDateTime(dt);
        }
        hc.$("#end-formatted").innerHTML = toFormatted;
    }

    function formatDateSpans() {
        hc.$$("span[data-dt]").forEach(function(el) {
            var dt = new Date(el.dataset.dt * 1000);
            el.innerText = dateFormatter.formatDate(dt, true);
        });
    }

    function updateNumHits() {
        var numHits = hc.$("#num-hits");
        if (numHits) {
            numHits.textContent = hc.$$("#log tr").length;
        }
    }

    function applyFilters() {
        var url = document.getElementById("log").dataset.refreshUrl;
        slider.disabled = slider.value == slider.max;
        var qs = hc.serialize("#filters").toString();
        slider.disabled = false;

        if (activeRequest) {
            // Abort the previous in-flight request so we don't display stale
            // data later
            activeRequest.abort();
        }
        var ctrl = new AbortController();
        activeRequest = ctrl;
        hc.get(url + "?" + qs, null, {timeout: 2000, signal: ctrl.signal}).then(function(r) {
            return r.text().then(function(data) {
                activeRequest = null;
                lastUpdated = r.headers.get("X-Last-Event-Timestamp");
                var tbody = document.createElement("tbody");
                tbody.innerHTML = data;
                formatPingDates(tbody.querySelectorAll("tr"));
                hc.$("#log").replaceChildren(tbody);
                updateNumHits();
            });
        }).catch(function() {});
    }

    hc.on("#end", "input", updateSliderPreview);
    hc.on("#end", "change", applyFilters);
    hc.on("#filters input[type=checkbox]", "change", applyFilters);

    hc.on("#log", "click", "tr.ok", function() {
        var n = this.querySelector("td").textContent;
        var tmpl = hc.$("#log").dataset.url.slice(0, -2);
        loadPingDetails(tmpl + n + "/");
        return false;
    });

    function formatPingDates(rows) {
        rows.forEach(function(row) {
            var dt = new Date(row.dataset.dt * 1000);
            row.children[1].textContent = dateFormatter.formatDate(dt);
            row.children[2].textContent = dateFormatter.formatTime(dt);
        })
    }

    hc.on("#tz-switcher", "click", "[data-tz]", function() {
        var button = this;
        hc.$$("#tz-switcher [data-tz]").forEach(function(el) {
            el.classList.toggle("active", el == button);
        });
        dateFormatter.setTimezone(button.dataset.tz);
        updateSliderPreview();
        formatDateSpans();
        formatPingDates(document.querySelectorAll("#log tr"));
    });

    updateSliderPreview();
    formatDateSpans();
    formatPingDates(document.querySelectorAll("#log tr"));
    // The table is initially hidden to avoid flickering as we convert dates.
    // Once it's ready, set it to visible:
    hc.$("#log").style.visibility = "visible";

    var lastUpdated = document.getElementById("last-event-timestamp").textContent;
    function fetchNewEvents() {
        // Do not fetch updates if the slider is not set to "now"
        // or there's an AJAX request in flight
        if (slider.value != slider.max || activeRequest) {
            return;
        }

        var url = document.getElementById("log").dataset.refreshUrl;
        var qs = hc.serialize("#filters").toString();

        if (lastUpdated) {
            qs += "&u=" + lastUpdated;
        }

        var ctrl = new AbortController();
        activeRequest = ctrl;
        hc.get(url + "?" + qs, null, {timeout: 2000, signal: ctrl.signal}).then(function(r) {
            return r.text().then(function(data) {
                activeRequest = null;
                if (!data)
                    return;

                lastUpdated = r.headers.get("X-Last-Event-Timestamp");
                var tbody = document.createElement("tbody");
                tbody.setAttribute("class", "new");
                tbody.innerHTML = data;
                formatPingDates(tbody.querySelectorAll("tr"));
                document.getElementById("log").prepend(tbody);
                updateNumHits();
            });
        }, function() {
            // A newer applyFilters() request may have replaced this one
            if (activeRequest == ctrl) {
                activeRequest = null;
            }
        });
    }

    adaptiveSetInterval(fetchNewEvents, false);
});
