function loadPingDetails(url) {
    var body = document.getElementById("ping-details-body");
    body.innerHTML = "<div class='loading'><div class='spinner'><div></div><div></div><div></div></div></div>";
    hc.showModal("#ping-details-modal");
    hc.$("#ping-details-body .spinner").classList.add("started");

    hc.getText(url).then(function(data) {
        body.innerHTML = data;

        // ping_details_not_found.html has no .times
        var times = hc.$("#ping-details-body .times");
        if (!times) return;

        var dateFormatter = new DateFormatter("UTC");
        var created = new Date(times.dataset.dt * 1000);
        hc.$$("#ping-details-body .times span").forEach(function(el) {
            dateFormatter.setTimezone(el.dataset.tz);
            el.innerText = dateFormatter.formatDateTime(created);
        });
    });
}
