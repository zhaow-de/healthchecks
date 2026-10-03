hc.ready(function () {
    const base = hc.base();
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const input = document.getElementById("schedule");

    let currentPreviewHash = "";
    function updateCronPreview() {
        const schedule = input.value;

        // Don't try preview with empty values, or if values have not changed
        if (!schedule || schedule === currentPreviewHash)
            return;

        // OK, we're good
        currentPreviewHash = schedule;
        hc.$$("#cron-preview-title").forEach(function(el) {
            el.textContent = "Updating...";
        });

        hc.post(base + "/checks/cron_preview/", {schedule: schedule, tz: tz}).then(function(r) {
            return r.text();
        }).then(function(data) {
            if (schedule !== currentPreviewHash) {
                return;  // ignore stale results
            }

            document.getElementById("cron-preview").innerHTML = data;
        });
    }

    hc.on("#common-cron-expressions button", "click", function() {
        input.value = this.closest("tr").querySelector("td:nth-child(2)").textContent;
        updateCronPreview();
    });

    hc.on(input, "keyup", updateCronPreview);
    updateCronPreview();
});
