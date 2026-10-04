hc.ready(function () {
    const base = hc.base();
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const input = document.getElementById("schedule");

    let currentPreviewHash = "";
    async function updateCronPreview() {
        const schedule = input.value;

        // Don't try preview with empty values, or if values have not changed
        if (!schedule || schedule === currentPreviewHash)
            return;

        // OK, we're good
        currentPreviewHash = schedule;
        hc.$$("#cron-preview-title").forEach(function(el) {
            el.textContent = "Updating...";
        });

        try {
            const r = await hc.post(base + "/checks/cron_preview/", {schedule: schedule, tz: tz});
            const data = await r.text();
            if (schedule !== currentPreviewHash) {
                return;  // ignore stale results
            }

            document.getElementById("cron-preview").innerHTML = data;
        } catch {
            if (schedule !== currentPreviewHash) {
                return;
            }

            // Forget the schedule, so that entering it again retries
            currentPreviewHash = "";
            document.getElementById("cron-preview").textContent = "Failed to load the preview.";
        }
    }

    hc.on("#common-cron-expressions button", "click", function() {
        input.value = this.closest("tr").querySelector("td:nth-child(2)").textContent;
        updateCronPreview();
    });

    hc.on(input, "keyup", updateCronPreview);
    updateCronPreview();
});
