hc.ready(function () {
    const base = hc.base();
    const period = document.getElementById("period-value");
    const periodUnit = document.getElementById("period-unit");
    const grace = document.getElementById("grace-value");
    const graceUnit = document.getElementById("grace-unit");
    const graceCron = document.getElementById("update-timeout-grace-cron");
    const graceCronUnit = document.getElementById("update-timeout-grace-cron-unit");
    const graceOncalendar = document.getElementById("update-timeout-grace-oncalendar");
    const graceOncalendarUnit = document.getElementById("update-timeout-grace-oncalendar-unit");


    hc.on(".timeout-grace", "click", function() {
        const row = this.closest("tr.checks-row");
        const code = row ? row.id : this.dataset.code;

        const url = base + "/checks/" + code + "/timeout/";

        hc.$$("#update-timeout-form, #update-cron-form, #update-oncalendar-form").forEach(function(form) {
            form.setAttribute("action", url);
        });

        // Simple, period
        const periodParsed = secsToUnits(this.dataset.timeout);
        period.value = periodParsed.value;
        periodUnit.value = periodParsed.unit;
        periodSlider.noUiSlider.set(this.dataset.timeout);
        hc.$("#update-timeout-timeout").value = this.dataset.timeout;

        // Simple, grace
        const graceParsed = secsToUnits(this.dataset.grace);
        grace.value = graceParsed.value;
        graceUnit.value = graceParsed.unit;
        graceSlider.noUiSlider.set(this.dataset.grace);
        hc.$("#update-timeout-grace").value = this.dataset.grace;

        // Cron
        cronPreviewHash = "";
        hc.$("#cron-preview").innerHTML = "<p>Updating...</p>";
        hc.$("#schedule").value = this.dataset.kind === "cron" ? this.dataset.schedule: "* * * * *";
        document.getElementById("tz").tomselect.setValue(this.dataset.tz, true);
        graceCron.value = graceParsed.value;
        graceCronUnit.value = graceParsed.unit;
        hc.$("#update-cron-grace").value = this.dataset.grace;
        updateCronPreview();

        // OnCalendar
        onCalendarPreviewHash = "";
        hc.$("#oncalendar-preview").innerHTML = "<p>Updating...</p>";
        hc.$("#schedule-oncalendar").value = this.dataset.kind === "oncalendar" ? this.dataset.schedule: "*-*-* *:*:*";
        document.getElementById("tz-oncalendar").tomselect.setValue(this.dataset.tz, true);
        graceOncalendar.value = graceParsed.value;
        graceOncalendarUnit.value = graceParsed.unit;
        hc.$("#update-oncalendar-grace").value = this.dataset.grace;
        updateOnCalendarPreview();

        showPanel(this.dataset.kind);
        hc.showModal("#update-timeout-modal");
        return false;
    });

    const secsToUnits = function(secs) {
        if (secs % 86400 === 0) {
            return {value: secs / 86400, unit: 86400}
        }
        if (secs % 3600 === 0) {
            return {value: secs / 3600, unit: 3600}
        }

        return {value: Math.round(secs / 60), unit: 60}
    }

    const pipLabels = {
        60: "1 minute",
        1800: "30 minutes",
        3600: "1 hour",
        43200: "12 hours",
        86400: "1 day",
        604800: "1 week",
        2592000: "30 days",
        31536000: "365 days"
    }

    const periodSlider = document.getElementById("period-slider");
    noUiSlider.create(periodSlider, {
        start: [20],
        connect: "lower",
        range: {
            'min': [60, 60],
            '30%': [3600, 3600],
            '60%': [86400, 86400],
            '75%': [604800, 86400],
            '90%': [2592000, 2592000],
            'max': 31536000
        },
        pips: {
            mode: 'values',
            values: [60, 1800, 3600, 43200, 86400, 604800, 2592000, 31536000],
            density: 4,
            format: {
                to: function(v) { return pipLabels[v] },
                from: function() {}
            }
        }
    });

    function setPeriod(secs) {
        // Set the hidden form field
        hc.$("#update-timeout-timeout").value = secs;
        // Set the visible value+units form fields
        const parsed = secsToUnits(secs);
        period.value = parsed.value;
        periodUnit.value = parsed.unit;
    }

    // Update inputs and the hidden field when user slides the period slider
    periodSlider.noUiSlider.on("slide", function(a, b, value) {
        setPeriod(Math.round(value));
    });

    // Update slider, inputs and the hidden field when user clicks slider labels
    hc.on("#period-slider .noUi-value", "click", function() {
        periodSlider.noUiSlider.set(this.dataset.value);
        setPeriod(this.dataset.value);
    });

    // Update the slider and the hidden field when user changes period inputs
    hc.on("#update-timeout-modal .period-input", "keyup change", function() {
        const secs = Math.round(period.value * periodUnit.value);
        period.setCustomValidity(secs <= 31536000 ? "" : "Must not exceed 365 days");

        if (secs >= 60) {
            periodSlider.noUiSlider.set(secs);
            hc.$("#update-timeout-timeout").value = secs;
        }
    });

    const graceSlider = document.getElementById("grace-slider");
    noUiSlider.create(graceSlider, {
        start: [20],
        connect: "lower",
        range: {
            'min': [60, 60],
            '30%': [3600, 3600],
            '60%': [86400, 86400],
            '75%': [604800, 86400],
            '90%': [2592000, 2592000],
            'max': 31536000
        },
        pips: {
            mode: 'values',
            values: [60, 1800, 3600, 43200, 86400, 604800, 2592000, 31536000],
            density: 4,
            format: {
                to: function(v) { return pipLabels[v] },
                from: function() {}
            }
        }
    });

    function setGrace(secs) {
        // Set the hidden form field
        hc.$("#update-timeout-grace").value = secs;
        // Set the visible value+units form fields
        const parsed = secsToUnits(secs);
        grace.value = parsed.value;
        graceUnit.value = parsed.unit;
    }

    // Update inputs and the hidden field when user slides the grace slider
    graceSlider.noUiSlider.on("slide", function(a, b, value) {
        setGrace(Math.round(value));
    });

    // Update slider, inputs and the hidden field when user clicks slider labels
    hc.on("#grace-slider .noUi-value", "click", function() {
        graceSlider.noUiSlider.set(this.dataset.value);
        setGrace(this.dataset.value);
    });

    // Update the slider and the hidden field when user changes grace inputs
    hc.on("#update-timeout-modal .grace-input", "keyup change", function() {
        const secs = Math.round(grace.value * graceUnit.value);
        grace.setCustomValidity(secs <= 31536000 ? "" : "Must not exceed 365 days");

        if (secs >= 60) {
            graceSlider.noUiSlider.set(secs);
            hc.$("#update-timeout-grace").value = secs;
        }
    });

    function showPanel(kind) {
        hc.toggle("#update-timeout-form", kind === "simple");
        hc.toggle("#update-cron-form", kind === "cron");
        hc.toggle("#update-oncalendar-form", kind === "oncalendar");
    }

    let cronPreviewHash = "";
    function updateCronPreview() {
        const schedule = hc.$("#schedule").value;
        const tz = hc.$("#tz").value;
        const hash = schedule + tz;

        // Don't try preview with empty values, or if values have not changed
        if (!schedule || !tz || hash === cronPreviewHash)
            return;

        // OK, we're good
        cronPreviewHash = hash;
        const title = hc.$("#cron-preview-title");
        if (title) title.textContent = "Updating...";

        const data = {schedule: schedule, tz: tz};
        hc.post(base + "/checks/cron_preview/", data).then((r) => r.text()).then(function(html) {
            if (hash !== cronPreviewHash) {
                return;  // ignore stale results
            }

            hc.$("#cron-preview").innerHTML = html;
            const haveError = hc.$("#invalid-arguments") !== null;
            hc.$("#update-cron-submit").disabled = haveError;
        });
    }

    let onCalendarPreviewHash = "";
    function updateOnCalendarPreview() {
        const schedule = hc.$("#schedule-oncalendar").value;
        const tz = hc.$("#tz-oncalendar").value;
        const hash = schedule + tz;

        // Don't try preview with empty values, or if values have not changed
        if (!schedule || !tz || hash === onCalendarPreviewHash)
            return;

        // OK, we're good
        onCalendarPreviewHash = hash;
        const title = hc.$("#oncalendar-preview-title");
        if (title) title.textContent = "Updating...";

        const data = {schedule: schedule, tz: tz};
        hc.post(base + "/checks/oncalendar_preview/", data).then((r) => r.text()).then(function(html) {
            if (hash !== onCalendarPreviewHash) {
                return;  // ignore stale results
            }

            hc.$("#oncalendar-preview").innerHTML = html;
            const haveError = hc.$("#invalid-oncalendar-arguments") !== null;
            hc.$("#update-oncalendar-submit").disabled = haveError;
        });
    }

    hc.on("#update-timeout-modal .update-timeout-grace-cron-input", "keyup change", function() {
        const secs = Math.round(graceCron.value * graceCronUnit.value);
        graceCron.setCustomValidity(secs <= 31536000 ? "" : "Must not exceed 365 days");

        if (secs >= 60) {
            hc.$("#update-cron-grace").value = secs;
        }
    });

    hc.on("#update-timeout-modal .update-timeout-grace-oncalendar-input", "keyup change", function() {
        const secs = Math.round(graceOncalendar.value * graceOncalendarUnit.value);
        graceOncalendar.setCustomValidity(secs <= 31536000 ? "" : "Must not exceed 365 days");

        if (secs >= 60) {
            hc.$("#update-oncalendar-grace").value = secs;
        }
    });

    // Wire up events for Timeout/Cron forms
    hc.on("#update-timeout-modal .kind-simple", "click", () => showPanel("simple"));
    hc.on("#update-timeout-modal .kind-cron", "click", () => showPanel("cron"));
    hc.on("#update-timeout-modal .kind-oncalendar", "click", () => showPanel("oncalendar"));

    hc.on("#schedule", "keyup", updateCronPreview);
    hc.on("#schedule-oncalendar", "keyup", updateOnCalendarPreview);
    hc.on("#tz", "change", updateCronPreview);
    hc.on("#tz-oncalendar", "change", updateOnCalendarPreview);

});
