hc.ready(function () {
    const base = hc.base();
    const modal = document.getElementById("add-check-modal");
    const period = document.getElementById("add-check-period");
    const periodUnit = document.getElementById("add-check-period-unit");
    const cronField = document.getElementById("add-check-schedule");
    const onCalendarField = document.getElementById("add-check-schedule-oncalendar");
    const grace = document.getElementById("add-check-grace");
    const graceUnit = document.getElementById("add-check-grace-unit");

    hc.tagSelect("#add-check-tags", hc.$$("#my-checks-tags div").map((el) => el.textContent));

    function selectedKind() {
        return hc.$("#add-check-modal input[name=kind]:checked").value;
    }

    function updateScheduleExtras() {
        const kind = selectedKind();
        modal.classList.remove("simple", "cron", "oncalendar");
        modal.classList.add(kind);
        // Include cron schedule in POST data only if kind = "cron"
        cronField.disabled = kind !== "cron";
        // Include OnCalendar schedule in POST data only if kind = "oncalendar"
        onCalendarField.disabled = kind !== "oncalendar";
    }

    // Show and hide fields when user clicks simple/cron/oncalendar radio buttons
    hc.on("#add-check-modal input[type=radio][name=kind]", "change", updateScheduleExtras);

    hc.on(modal, "shown.bs.modal", function() {
        updateScheduleExtras();
        validateSchedule();
        document.getElementById("add-check-tz").tomselect.setValue("UTC", true);
        document.getElementById("add-check-name").focus();

        // Pre-select the currently active tags
        const selectedTags = hc.$$("#my-checks-tags .checked").map((el) => el.textContent);
        document.getElementById("add-check-tags").tomselect.setValue(selectedTags);
    });

    bindDuration({value: period, unit: periodUnit, hidden: hc.$("input[name=timeout]", modal)});
    bindDuration({value: grace, unit: graceUnit, hidden: hc.$("input[name=grace]", modal)});

    let currentSchedule = "";
    async function validateSchedule() {
        const kind = selectedKind();
        if (kind === "simple") return;

        const field = kind === "cron" ? cronField : onCalendarField;

        // Return early if the schedule has not changed
        if (field.value === currentSchedule)
            return;

        const schedule = field.value;
        currentSchedule = schedule;
        try {
            const data = await hc.getJSON(base + "/checks/validate_schedule/", {kind: kind, schedule: schedule});
            if (schedule !== currentSchedule)
                return;  // ignore stale results

            field.setCustomValidity(data.result ? "" : "Please enter a valid expression");
        } catch {
            if (schedule !== currentSchedule)
                return;

            // Forget the schedule, so that the next edit retries, and leave the
            // check to the server instead of keeping an earlier verdict
            currentSchedule = "";
            field.setCustomValidity("");
        }
    }

    hc.on("#add-check-schedule", "keyup change", validateSchedule);
    hc.on("#add-check-schedule-oncalendar", "keyup change", validateSchedule);
});
