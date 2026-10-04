hc.ready(function () {
    const base = hc.base();
    const favicon = document.querySelector('link[rel="icon"]');

    hc.on("#edit-name", "click", function() {
        hc.showModal("#update-name-modal");
        hc.$("#update-name-input").focus();

        return false;
    });

    // Configure Tom-Select for entering tags
    function toOption(tag) {
        return {value: tag}
    }

    const allTags = document.getElementById("update-tags-input").getAttribute("data-all-tags");
    const options = allTags ? allTags.split(" ").map(toOption) : [];
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
        render: {no_results: () => ""},
        searchField: ["value"],
    });

    hc.on("#new-check-alert a", "click", function() {
        const target = document.getElementById(this.dataset.target);
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

    hc.on("#ping-now", "click", function() {
        const button = this;
        hc.post(this.dataset.url).then(function() {
            button.textContent = "Success!";
        }).catch(function() {});
    });

    hc.on("#ping-now", "mouseout", function(e) {
        setTimeout(function() {
            e.target.textContent = "Ping Now!";
        }, 300);
    });

    hc.on(".details-integrations tr", "click", function() {
        const row = this;
        const badge = row.querySelector(".badge");
        const isOn = row.classList.toggle("on");
        badge.textContent = isOn ? "ON" : "OFF";
        hc.post(row.dataset.url, {"state": isOn ? "on" : "off"}).catch(function() {
            // The change was not saved: show the state the server still has
            row.classList.toggle("on", !isOn);
            badge.textContent = isOn ? "OFF" : "ON";
        });
    });

    const statusUrl = document.getElementById("events").dataset.statusUrl;
    // Look up the active tz switch to determine the initial display timezone:
    const activeTz = hc.$("#tz-switcher .active");
    const dateFormatter = new DateFormatter(activeTz ? activeTz.dataset.tz : undefined);
    let lastStatusText = "";
    let lastUpdated = "";
    let lastStarted = false;
    adaptiveSetInterval(function() {
        const url = statusUrl + (lastUpdated ? "?u=" + lastUpdated : "");
        hc.getJSON(url, null, {timeout: 2000}).then(function(data) {
            if (data.status_text !== lastStatusText) {
                lastStatusText = data.status_text;
                hc.$("#current-status-icon").className = "status ic-" + data.status;
                hc.$("#current-status-text").innerHTML = data.status_text;

                const pauseBtn = hc.$("#pause-btn");
                if (pauseBtn) {
                    pauseBtn.disabled = data.status === "paused" && !data.started;
                }
            }

            if (data.started !== lastStarted) {
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

            if (document.title !== data.title) {
                document.title = data.title;
                const downPostfix = data.status === "down" ? "_down" : "";
                favicon.href = `${base}/static/img/favicon${downPostfix}.svg`;
            }
        }).catch(function() {});
    }, true);

    hc.on("#events", "click", "tr.ok", function() {
        const n = this.querySelector("td").textContent;
        const tmpl = hc.$("#log").dataset.url.slice(0, -2);
        loadPingDetails(tmpl + n + "/");
        return false;
    });

    function formatPingDates() {
        document.querySelectorAll("#log tr").forEach(function(row) {
            const dt = new Date(row.dataset.dt * 1000);
            row.children[1].textContent = dateFormatter.formatDate(dt);
            row.children[2].textContent = dateFormatter.formatTime(dt);
        })

        // The table is initially hidden to avoid flickering as we convert dates.
        // Once it's ready, set it to visible:
        const log = hc.$("#log");
        if (log) log.style.visibility = "visible";
    }

    hc.on("#tz-switcher", "click", "[data-tz]", function() {
        const button = this;
        hc.$$("#tz-switcher [data-tz]").forEach(function(el) {
            el.classList.toggle("active", el === button);
        });
        dateFormatter.setTimezone(button.dataset.tz);
        formatPingDates();
    });

    // #transfer-modal keeps a static .modal-dialog (Bootstrap caches it when the
    // instance is created): the form loads into its .modal-content.
    let transferFormLoadStarted = false;
    hc.on("#transfer-btn", "mouseenter click", async function() {
        if (transferFormLoadStarted)
            return;

        transferFormLoadStarted = true;
        const content = hc.$("#transfer-modal .modal-content");
        try {
            content.innerHTML = await hc.getText(this.dataset.url);
        } catch {
            // Let the next hover or click try again
            transferFormLoadStarted = false;
            content.innerHTML = "<div class='modal-body'>Failed to load.</div>";
        }
    });

    hc.$$(".click-to-copy").forEach(function(el) {
        hc.tooltip(el, {title: "Click to copy"});
        el.addEventListener("click", function() {
            if (window.getSelection().toString()) {
                // do nothing, selection not empty
                return;
            }

            navigator.clipboard.writeText(el.textContent).then(
                () => hc.flashTooltip(el, "Copied!", "Click to copy"),
                () => hc.flashTooltip(el, "Copy failed", "Click to copy"),
            );
        });
    });

    // Enable the submit button in transfer form when user selects
    // the target project:
    hc.on("#transfer-modal", "change", "#target-project", function() {
        hc.$("#transfer-confirm").disabled = !this.value;
    });


    // Enable/disable fields in the "Filtering Rules" modal
    hc.on("input.filter-toggle", "change", function() {
        const enableInputs = hc.$$("input.filter-toggle:checked").length > 0;
        hc.$$(".filter-kw").forEach(function(el) {
            el.disabled = !enableInputs;
        });
    });

    // If the URL hash is #ping-<number>,  open the "Ping Details" dialog
    if (document.location.hash.indexOf("#ping-") === 0) {
        const n = parseInt(document.location.hash.slice(6));
        loadPingDetails(`../pings/${n}/`);
    }

});
