hc.ready(function () {
    var base = hc.base();
    var favicon = document.querySelector('link[rel="icon"]');

    hc.on("#edit-name", "click", function() {
        hc.showModal("#update-name-modal");
        hc.$("#update-name-input").focus();

        return false;
    });

    // Configure Tom-Select for entering tags
    function toOption(tag) {
        return {value: tag}
    }

    var allTags = document.getElementById("update-tags-input").getAttribute("data-all-tags");
    var options = allTags ? allTags.split(" ").map(toOption) : [];
    new TomSelect("#update-tags-input", {
        create: true,
        createOnBlur: true,
        delimiter: " ",
        diacritics: false,
        hideSelected: true,
        highlight: false,
        labelField: "value",
        options: options,
        refreshThrottle: 0,
        render: {no_results:(data, escape) => ""},
        searchField: ["value"],
    });

    hc.on("#new-check-alert a", "click", function() {
        var target = document.getElementById(this.dataset.target);
        if (target) target.click();
        return false;
    });

    hc.on("#edit-desc", "click", function() {
        hc.showModal("#update-name-modal");
        hc.$("#update-desc-input").focus();

        return false;
    });

    hc.on("#current-status-text", "click", "#resume-btn", function() {
        hc.$("#resume-form").submit();
        return false;
    });

    // The ping URL may be on another origin: hc.post sends no custom headers
    // there, so the request stays simple and needs no CORS preflight.
    hc.on("#ping-now", "click", function() {
        var button = this;
        hc.post(this.dataset.url).then(function() {
            button.textContent = "Success!";
        }).catch(function() {});
    });

    hc.on("#ping-now", "mouseout", function(e) {
        setTimeout(function() {
            e.target.textContent = "Ping Now!";
        }, 300);
    });

    hc.on(".details-integrations.rw tr", "click", function() {
        var isOn = this.classList.toggle("on");
        this.querySelector(".badge").textContent = isOn ? "ON" : "OFF";
        hc.post(this.dataset.url, {"state": isOn ? "on" : "off"}).catch(function() {});
    });

    var statusUrl = document.getElementById("events").dataset.statusUrl;
    // Look up the active tz switch to determine the initial display timezone:
    var activeTz = hc.$("#tz-switcher .active");
    var dateFormatter = new DateFormatter(activeTz ? activeTz.dataset.tz : undefined);
    var lastStatusText = "";
    var lastUpdated = "";
    var lastStarted = false;
    adaptiveSetInterval(function() {
        var url = statusUrl + (lastUpdated ? "?u=" + lastUpdated : "");
        hc.getJSON(url, null, {timeout: 2000}).then(function(data) {
            if (data.status_text != lastStatusText) {
                lastStatusText = data.status_text;
                hc.$("#current-status-icon").className = "status ic-" + data.status;
                hc.$("#current-status-text").innerHTML = data.status_text;

                var pauseBtn = hc.$("#pause-btn");
                if (pauseBtn) {
                    pauseBtn.disabled = data.status == "paused" && !data.started;
                }
            }

            if (data.started != lastStarted) {
                lastStarted = data.started;
                hc.$("#current-status-spinner").classList.toggle("started", !!data.started);
            }

            if (data.events) {
                lastUpdated = data.updated;
                hc.$("#log-container").innerHTML = data.events;
                formatPingDates();
            }

            if (data.downtimes) {
                hc.$("#downtimes").innerHTML = data.downtimes;
            }

            if (document.title != data.title) {
                document.title = data.title;
                var downPostfix = data.status == "down" ? "_down" : "";
                favicon.href = `${base}/static/img/favicon${downPostfix}.svg`;
            }
        }).catch(function() {});
    }, true);

    hc.on("#events", "click", "tr.ok", function() {
        var n = this.querySelector("td").textContent;
        var tmpl = hc.$("#log").dataset.url.slice(0, -2);
        loadPingDetails(tmpl + n + "/");
        return false;
    });

    function formatPingDates() {
        document.querySelectorAll("#log tr").forEach(function(row) {
            var dt = new Date(row.dataset.dt * 1000);
            row.children[1].textContent = dateFormatter.formatDate(dt);
            row.children[2].textContent = dateFormatter.formatTime(dt);
        })

        // The table is initially hidden to avoid flickering as we convert dates.
        // Once it's ready, set it to visible:
        var log = hc.$("#log");
        if (log) log.style.visibility = "visible";
    }

    hc.on("#tz-switcher", "click", "[data-tz]", function() {
        var button = this;
        hc.$$("#tz-switcher [data-tz]").forEach(function(el) {
            el.classList.toggle("active", el == button);
        });
        dateFormatter.setTimezone(button.dataset.tz);
        formatPingDates();
    });

    // #transfer-modal keeps a static .modal-dialog (Bootstrap caches it when the
    // instance is created): the form loads into its .modal-content.
    var transferFormLoadStarted = false;
    hc.on("#transfer-btn", "mouseenter click", function() {
        if (transferFormLoadStarted)
            return;

        transferFormLoadStarted = true;
        hc.getText(this.dataset.url).then(function(data) {
            hc.$("#transfer-modal .modal-content").innerHTML = data;
        });
    });

    hc.$$(".click-to-copy").forEach(function(el) {
        hc.tooltip(el, {title: "Click to copy"});
        el.addEventListener("click", function() {
            if (window.getSelection().toString()) {
                // do nothing, selection not empty
                return;
            }

            navigator.clipboard.writeText(el.textContent);
            hc.flashTooltip(el, "Copied!", "Click to copy");
        });
    });

    // Enable the submit button in transfer form when user selects
    // the target project:
    hc.on("#transfer-modal", "change", "#target-project", function() {
        hc.$("#transfer-confirm").disabled = !this.value;
    });


    // Enable/disable fields in the "Filtering Rules" modal
    hc.on("input.filter-toggle", "change", function() {
        var enableInputs = hc.$$("input.filter-toggle:checked").length > 0;
        hc.$$(".filter-kw").forEach(function(el) {
            el.disabled = !enableInputs;
        });
    });

    // If the URL hash is #ping-<number>,  open the "Ping Details" dialog
    if (document.location.hash.indexOf("#ping-") === 0) {
        var n = parseInt(document.location.hash.substr(6));
        loadPingDetails(`../pings/${n}/`);
    }

});
