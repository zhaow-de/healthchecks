// The schedule inputs shared by the timeout dialog (update-timeout-modal.js), the add-check
// dialog (add-check-modal.js) and the cron cheatsheet (docs_cron.js). makeSlider needs
// nouislider.min.js on the page.

// Seconds as {value, unit}, in the largest of days, hours and minutes that divides them.
function secsToUnits(secs) {
    if (secs % 86400 === 0) {
        return {value: secs / 86400, unit: 86400};
    }
    if (secs % 3600 === 0) {
        return {value: secs / 3600, unit: 3600};
    }

    return {value: Math.round(secs / 60), unit: 60};
}

// A noUiSlider on el from 1 minute to 365 days, with labelled stops.
function makeSlider(el) {
    const pipLabels = {
        60: "1 minute",
        1800: "30 minutes",
        3600: "1 hour",
        43200: "12 hours",
        86400: "1 day",
        604800: "1 week",
        2592000: "30 days",
        31536000: "365 days"
    };

    noUiSlider.create(el, {
        start: [20],
        connect: "lower",
        range: {
            "min": [60, 60],
            "30%": [3600, 3600],
            "60%": [86400, 86400],
            "75%": [604800, 86400],
            "90%": [2592000, 2592000],
            "max": 31536000
        },
        pips: {
            mode: "values",
            values: [60, 1800, 3600, 43200, 86400, 604800, 2592000, 31536000],
            density: 4,
            format: {
                to: function(v) { return pipLabels[v]; },
                from: function() {}
            }
        }
    });
    return el.noUiSlider;
}

// Keeps a duration's number input, its unit select, the hidden field that posts it in
// seconds and, when given, its slider in step. Returns set(secs), which shows secs in
// all of them.
function bindDuration({value, unit, hidden, slider}) {
    function show(secs) {
        hidden.value = secs;
        const parsed = secsToUnits(secs);
        value.value = parsed.value;
        unit.value = parsed.unit;
        value.setCustomValidity("");
    }

    hc.on([value, unit], "keyup change", function() {
        const secs = Math.round(value.value * unit.value);
        value.setCustomValidity(secs <= 31536000 ? "" : "Must not exceed 365 days");

        if (secs >= 60) {
            if (slider) slider.set(secs);
            hidden.value = secs;
        }
    });

    if (slider) {
        slider.on("slide", function(values, handle, unencoded) {
            show(Math.round(unencoded[handle]));
        });

        // A click on one of the slider's labels
        hc.on(slider.target, "click", ".noUi-value", function() {
            slider.set(this.dataset.value);
            show(this.dataset.value);
        });
    }

    return function set(secs) {
        if (slider) slider.set(secs);
        show(secs);
    };
}

// Loads url's preview of the schedule in `input`, in the time zone `tz` (a select, or a
// zone name), into `target` whenever either changes. While the preview reports an error,
// `submit`, when given, is disabled. Returns refresh(), which shows "Updating..." and
// loads the preview again even when the values have not changed.
function schedulePreview({input, tz, url, target, submit}) {
    // The values of the preview shown or loading, so an unchanged input loads nothing
    let current = "";

    async function update() {
        const schedule = input.value;
        const zone = typeof tz === "string" ? tz : tz.value;
        const values = schedule + zone;
        if (!schedule || !zone || values === current) return;

        current = values;
        const title = target.querySelector("[id$='-preview-title']");
        if (title) title.textContent = "Updating...";

        try {
            const r = await hc.post(url, {schedule: schedule, tz: zone});
            const html = await r.text();
            if (values !== current) return;  // a newer request replaced this one

            target.innerHTML = html;
            if (submit) submit.disabled = target.querySelector("[id^='invalid-']") !== null;
        } catch {
            if (values !== current) return;

            // Forget the values, so that entering them again retries
            current = "";
            target.textContent = "Failed to load the preview.";
        }
    }

    hc.on(input, "keyup", update);
    if (typeof tz !== "string") hc.on(tz, "change", update);

    return function refresh() {
        current = "";
        target.innerHTML = "<p>Updating...</p>";
        update();
    };
}
