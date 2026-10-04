hc.ready(function () {
    const base = hc.base();
    const byId = (id) => document.getElementById(id);

    const setPeriod = bindDuration({
        value: byId("period-value"),
        unit: byId("period-unit"),
        hidden: byId("update-timeout-timeout"),
        slider: makeSlider(byId("period-slider")),
    });
    const setGrace = bindDuration({
        value: byId("grace-value"),
        unit: byId("grace-unit"),
        hidden: byId("update-timeout-grace"),
        slider: makeSlider(byId("grace-slider")),
    });
    const setCronGrace = bindDuration({
        value: byId("update-timeout-grace-cron"),
        unit: byId("update-timeout-grace-cron-unit"),
        hidden: byId("update-cron-grace"),
    });
    const setOnCalendarGrace = bindDuration({
        value: byId("update-timeout-grace-oncalendar"),
        unit: byId("update-timeout-grace-oncalendar-unit"),
        hidden: byId("update-oncalendar-grace"),
    });

    const refreshCronPreview = schedulePreview({
        input: byId("schedule"),
        tz: byId("tz"),
        url: base + "/checks/cron_preview/",
        target: byId("cron-preview"),
        submit: byId("update-cron-submit"),
    });
    const refreshOnCalendarPreview = schedulePreview({
        input: byId("schedule-oncalendar"),
        tz: byId("tz-oncalendar"),
        url: base + "/checks/oncalendar_preview/",
        target: byId("oncalendar-preview"),
        submit: byId("update-oncalendar-submit"),
    });

    function showPanel(kind) {
        hc.toggle("#update-timeout-form", kind === "simple");
        hc.toggle("#update-cron-form", kind === "cron");
        hc.toggle("#update-oncalendar-form", kind === "oncalendar");
    }

    // A check row's period cell on the checks page, the "Change Schedule" button on
    // the details page
    hc.on(".timeout-grace", "click", function() {
        const row = this.closest("tr.checks-row");
        const code = row ? row.id : this.dataset.code;

        const url = base + "/checks/" + code + "/timeout/";
        hc.$$("#update-timeout-form, #update-cron-form, #update-oncalendar-form").forEach(function(form) {
            form.setAttribute("action", url);
        });

        const check = this.dataset;
        setPeriod(check.timeout);
        setGrace(check.grace);
        setCronGrace(check.grace);
        setOnCalendarGrace(check.grace);

        byId("schedule").value = check.kind === "cron" ? check.schedule : "* * * * *";
        byId("tz").tomselect.setValue(check.tz, true);
        refreshCronPreview();

        byId("schedule-oncalendar").value = check.kind === "oncalendar" ? check.schedule : "*-*-* *:*:*";
        byId("tz-oncalendar").tomselect.setValue(check.tz, true);
        refreshOnCalendarPreview();

        showPanel(check.kind);
        hc.showModal("#update-timeout-modal");
        return false;
    });

    hc.on("#update-timeout-modal .kind-simple", "click", () => showPanel("simple"));
    hc.on("#update-timeout-modal .kind-cron", "click", () => showPanel("cron"));
    hc.on("#update-timeout-modal .kind-oncalendar", "click", () => showPanel("oncalendar"));
});
