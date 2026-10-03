hc.ready(function () {
    var base = hc.base();
    var modal = document.getElementById("add-check-modal");
    var period = document.getElementById("add-check-period");
    var periodUnit = document.getElementById("add-check-period-unit");
    var cronField = document.getElementById("add-check-schedule");
    var onCalendarField = document.getElementById("add-check-schedule-oncalendar");
    var grace = document.getElementById("add-check-grace");
    var graceUnit = document.getElementById("add-check-grace-unit");

    function divToOption(el) {
        return {value: el.textContent};
    }

    new TomSelect("#add-check-tags", {
        create: true,
        createOnBlur: true,
        delimiter: " ",
        diacritics: false,
        hideSelected: true,
        highlight: false,
        labelField: "value",
        options: hc.$$("#my-checks-tags div").map(divToOption),
        refreshThrottle: 0,
        render: {no_results:(data, escape) => ""},
        searchField: ["value"],
    });

    function selectedKind() {
        return hc.$("#add-check-modal input[name=kind]:checked").value;
    }

    function updateScheduleExtras() {
        var kind = selectedKind();
        modal.classList.remove("simple", "cron", "oncalendar");
        modal.classList.add(kind);
        // Include cron schedule in POST data only if kind = "cron"
        cronField.disabled = kind != "cron";
        // Include OnCalendar schedule in POST data only if kind = "oncalendar"
        onCalendarField.disabled = kind != "oncalendar";
    }

    // Show and hide fields when user clicks simple/cron/oncalendar radio buttons
    hc.on("#add-check-modal input[type=radio][name=kind]", "change", updateScheduleExtras);

    hc.on(modal, "shown.bs.modal", function() {
        updateScheduleExtras();
        validateSchedule();
        document.getElementById("add-check-tz").tomselect.setValue("UTC", true);
        document.getElementById("add-check-name").focus();

        // Pre-select the currently active tags
        var selectedTags = hc.$$("#my-checks-tags .checked").map((el) => el.textContent);
        document.getElementById("add-check-tags").tomselect.setValue(selectedTags);
    });

    // Update the hidden field when user changes period inputs
    hc.on("#add-check-modal .period-input", "keyup change", function() {
        var secs = Math.round(period.value * periodUnit.value);
        period.setCustomValidity(secs <= 31536000 ? "" : "Must not exceed 365 days");

        if (secs >= 60) {
            hc.$("#add-check-modal input[name=timeout]").value = secs;
        }
    });

    // Update the hidden field when user changes grace inputs
    hc.on("#add-check-modal .grace-input", "keyup change", function() {
        var secs = Math.round(grace.value * graceUnit.value);
        grace.setCustomValidity(secs <= 31536000 ? "" : "Must not exceed 365 days");

        if (secs >= 60) {
            hc.$("#add-check-modal input[name=grace]").value = secs;
        }
    });

    var currentSchedule = "";
    function validateSchedule() {
        var kind = selectedKind();
        if (kind == "simple") return;

        var field = kind == "cron" ? cronField : onCalendarField;

        // Return early if the schedule has not changed
        if (field.value == currentSchedule)
            return;

        currentSchedule = field.value;
        var payload = {kind: kind, schedule: field.value};
        hc.getJSON(base + "/checks/validate_schedule/", payload).then(function(data) {
            if (field.value != currentSchedule)
                return;  // ignore stale results

            field.setCustomValidity(data.result ? "" : "Please enter a valid expression");
        });
    }

    hc.on("#add-check-schedule", "keyup change", validateSchedule);
    hc.on("#add-check-schedule-oncalendar", "keyup change", validateSchedule);
});
