hc.ready(function () {
    // The AbortController of the request in flight, or null
    let activeRequest = null;
    const slider = document.getElementById("end");

    // Look up the active tz switch to determine the initial display timezone:
    const activeTz = hc.$("#tz-switcher .active");
    const dateFormatter = new DateFormatter(activeTz ? activeTz.dataset.tz : undefined);

    function updateSliderPreview() {
        let toFormatted = "now, live updates";
        if (slider.value !== slider.max) {
            const dt = new Date(slider.value * 1000);
            toFormatted = dateFormatter.formatDateTime(dt);
        }
        hc.$("#end-formatted").innerHTML = toFormatted;
    }

    function formatDateSpans() {
        hc.$$("span[data-dt]").forEach(function(el) {
            const dt = new Date(el.dataset.dt * 1000);
            el.innerText = dateFormatter.formatDate(dt, true);
        });
    }

    function updateNumHits() {
        const numHits = hc.$("#num-hits");
        if (numHits) {
            numHits.textContent = hc.$$("#log tr").length;
        }
    }

    async function applyFilters() {
        const url = document.getElementById("log").dataset.refreshUrl;
        slider.disabled = slider.value === slider.max;
        const qs = hc.serialize("#filters").toString();
        slider.disabled = false;

        if (activeRequest) {
            // Abort the previous in-flight request so we don't display stale
            // data later
            activeRequest.abort();
        }
        const ctrl = new AbortController();
        activeRequest = ctrl;
        try {
            const r = await hc.get(url + "?" + qs, null, {timeout: 2000, signal: ctrl.signal});
            const data = await r.text();
            const tbody = document.createElement("tbody");
            tbody.innerHTML = data;
            formatPingDates(tbody.querySelectorAll("tr"));
            hc.$("#log").replaceChildren(tbody);
            updateNumHits();
            lastUpdated = r.headers.get("X-Last-Event-Timestamp");
        } catch {
            // Aborted, timed out or failed: the table keeps its rows
        } finally {
            // A newer applyFilters() request may have replaced this one
            if (activeRequest === ctrl) {
                activeRequest = null;
            }
        }
    }

    hc.on("#end", "input", updateSliderPreview);
    hc.on("#end", "change", applyFilters);
    hc.on("#filters input[type=checkbox]", "change", applyFilters);

    hc.on("#log", "click", "tr.ok", function() {
        const n = this.querySelector("td").textContent;
        const tmpl = hc.$("#log").dataset.url.slice(0, -2);
        loadPingDetails(tmpl + n + "/");
        return false;
    });

    function formatPingDates(rows) {
        rows.forEach(function(row) {
            const dt = new Date(row.dataset.dt * 1000);
            row.children[1].textContent = dateFormatter.formatDate(dt);
            row.children[2].textContent = dateFormatter.formatTime(dt);
        })
    }

    hc.on("#tz-switcher", "click", "[data-tz]", function() {
        const button = this;
        hc.$$("#tz-switcher [data-tz]").forEach(function(el) {
            el.classList.toggle("active", el === button);
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

    // The timestamp of the newest event shown, or empty while the log shows none
    let lastUpdated = document.getElementById("last-event-timestamp").textContent;
    async function fetchNewEvents() {
        // Do not fetch updates if the slider is not set to "now"
        // or there's an AJAX request in flight
        if (slider.value !== slider.max || activeRequest) {
            return;
        }

        const url = document.getElementById("log").dataset.refreshUrl;
        // Without a shown event, ask for the events after the page load (the
        // slider's max): without u the server returns events up to "end" only
        const qs = hc.serialize("#filters").toString() + "&u=" + (lastUpdated || slider.max);

        const ctrl = new AbortController();
        activeRequest = ctrl;
        try {
            const r = await hc.get(url + "?" + qs, null, {timeout: 2000, signal: ctrl.signal});
            const data = await r.text();
            if (!data)
                return;

            const tbody = document.createElement("tbody");
            tbody.setAttribute("class", "new");
            tbody.innerHTML = data;
            formatPingDates(tbody.querySelectorAll("tr"));
            document.getElementById("log").prepend(tbody);
            updateNumHits();
            lastUpdated = r.headers.get("X-Last-Event-Timestamp");
        } catch {
            // Aborted, timed out or failed: the next run tries again
        } finally {
            // A newer applyFilters() request may have replaced this one
            if (activeRequest === ctrl) {
                activeRequest = null;
            }
        }
    }

    adaptiveSetInterval(fetchNewEvents, false);
});
