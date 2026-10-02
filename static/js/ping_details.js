function loadPingDetails(url) {
    $("#ping-details-body").html("<div class='loading'><div class='spinner'><div></div><div></div><div></div></div></div>");
    $('#ping-details-modal').modal("show");
    $("#ping-details-body .spinner").addClass("started");

    $.get(url, function(data) {
            $("#ping-details-body").html(data);

            var dateFormatter = new DateFormatter("UTC");
            var createdUnix = $("#ping-details-body .times").data("dt");
            var created = new Date(createdUnix * 1000);
            $("#ping-details-body .times span").each(function(i, el) {
                dateFormatter.setTimezone(el.dataset.tz);
                el.innerText = dateFormatter.formatDateTime(created);
            });
        }
    );
}
