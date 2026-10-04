hc.ready(function () {
    const input = document.getElementById("schedule");
    const preview = schedulePreview({
        input: input,
        tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
        url: hc.base() + "/checks/cron_preview/",
        target: document.getElementById("cron-preview"),
    });

    hc.on("#common-cron-expressions button", "click", function() {
        input.value = this.closest("tr").querySelector("td:nth-child(2)").textContent;
        preview.update();
    });

    preview.update();
});
