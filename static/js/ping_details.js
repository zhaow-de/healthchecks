async function loadPingDetails(url) {
    const body = document.getElementById("ping-details-body");
    body.innerHTML = "<div class='loading'><div class='spinner'><div></div><div></div><div></div></div></div>";
    hc.showModal("#ping-details-modal");
    hc.$("#ping-details-body .spinner").classList.add("started");

    try {
        body.innerHTML = await hc.getText(url);
    } catch {
        body.innerHTML = "<div class='modal-body'>Failed to load.</div>";
        return;
    }

    // ping_details_not_found.html has no .times
    const times = hc.$("#ping-details-body .times");
    if (!times) return;

    const dateFormatter = new DateFormatter("UTC");
    const created = new Date(times.dataset.dt * 1000);
    hc.$$("#ping-details-body .times span").forEach(function(el) {
        dateFormatter.setTimezone(el.dataset.tz);
        el.innerText = dateFormatter.formatDateTime(created);
    });
}

// On the details and log pages, the dialog's data-url is the URL of the check's
// ping #0: a click on a ping in the event log (#log, which the details page
// replaces as it refreshes) opens that ping, and so does a #ping-<n> hash, which
// the alert emails link to.
hc.ready(function() {
    const modal = document.getElementById("ping-details-modal");
    const url = modal && modal.dataset.url;
    if (!url) return;

    function open(n) {
        loadPingDetails(url.replace(/0\/$/, n + "/"));
    }

    hc.on(document, "click", "#log tr.ok", function() {
        open(this.querySelector("td").textContent);
        return false;
    });

    const m = window.location.hash.match(/^#ping-(\d+)$/);
    if (m) open(m[1]);
});
