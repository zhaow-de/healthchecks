hc.ready(function () {
    const base = hc.base();

    // Check codes are UUIDs and may start with a digit, which is not a valid
    // "#id" CSS selector, so rows are looked up with getElementById.
    function rowEl(code, selector) {
        const row = document.getElementById(code);
        return row && row.querySelector(selector);
    }

    function rowCode(el) {
        return el.closest("tr.checks-row").id;
    }

    hc.on(".my-checks-name", "click", function () {
        const url = base + "/checks/" + rowCode(this) + "/name/";

        hc.$("#update-name-form").setAttribute("action", url);
        hc.$("#update-name-input").value = this.dataset.name;
        hc.$("#update-slug-input").value = this.dataset.slug;

        const tagsTs = document.getElementById("update-tags-input").tomselect;
        tagsTs.setValue(this.dataset.tags.split(" "));

        hc.$("#update-desc-input").value = this.dataset.desc;
        hc.showModal("#update-name-modal");
        hc.$("#update-name-input").focus();

        return false;
    });

    function channelEl(span) {
        const idx = Array.from(span.parentElement.children).indexOf(span);
        return document.getElementById("ch-" + idx);
    }

    hc.tooltips("#checks-table", ".integrations span", {
        title: function () {
            return channelEl(this).dataset.title;
        },
    });

    hc.on(".integrations", "click", "span", function () {
        const isOff = this.classList.toggle("off");
        const checkCode = rowCode(this);
        const channelCode = channelEl(this).dataset.code;

        const url =
            base + "/checks/" + checkCode + "/channels/" + channelCode + "/enabled";

        const el = this;
        hc.post(url, { state: isOff ? "off" : "on" }).catch(function () {
            // The change was not saved: show the state the server still has
            el.classList.toggle("off", !isOff);
        });

        return false;
    });

    hc.on(".last-ping", "click", function () {
        if (this.innerText === "Never") {
            return false;
        }
        const code = rowCode(this);
        const lastPingUrl = base + "/checks/" + code + "/last_ping/";
        loadPingDetails(lastPingUrl);

        const logUrl = base + "/checks/" + code + "/log/";
        hc.$("#ping-details-log").setAttribute("href", logUrl);

        return false;
    });

    const table = document.getElementById("checks-table");
    const profileTz = table ? table.dataset.profileTz : undefined;
    const dateFormatter = new DateFormatter(profileTz);
    hc.tooltip(".last-ping", {
        delay: 200,
        title: function () {
            if (this.querySelector(".label-confirmation")) {
                return 'The word "confirm" was found in request body';
            }
            const dtSpan = this.querySelector("[data-dt]");
            if (dtSpan) {
                const dt = new Date(dtSpan.dataset.dt * 1000);
                return dateFormatter.formatTimestamp(dt);
            }
        },
    });

    // Hover only: a clicked chip keeps focus, and the default focus trigger would keep its tooltip open
    hc.tooltip("#my-checks-tags .btn", {
        title: function () {
            return this.getAttribute("data-tooltip");
        },
        trigger: "hover",
    });

    function statusMatch(el, statuses) {
        const statusClassList = el.querySelector(".status").classList;
        // Go through currently active status filters, and, for each,
        // check if the current check matches
        for (const status of statuses) {
            if (
                status === "started" &&
                el.querySelector(".spinner").classList.contains("started")
            ) {
                return true;
            }
            if (statusClassList.contains("ic-" + status)) {
                return true;
            }
        }
        return false;
    }

    function activeStatusButtons() {
        return hc.$$(".filter-btn").filter(hc.isVisible);
    }

    function applyFilters() {
        const url = new URL(window.location.href);
        url.search = "";

        // Checked tags
        const checked = hc.$$("#my-checks-tags .checked").map((el) => el.textContent);
        checked.forEach((tag) => url.searchParams.append("tag", tag));

        // Search string
        const searchInput = document.getElementById("search");
        const search = searchInput ? searchInput.value.toLowerCase() : "";
        if (search) {
            url.searchParams.append("search", search);
        }

        // Status filters
        const statuses = activeStatusButtons().map((el) => el.dataset.value);
        statuses.forEach((status) => url.searchParams.append("status", status));

        window.history.replaceState({}, "", url.toString());

        // Update sort links
        document.querySelectorAll("a[data-sort-value]").forEach((a) => {
            url.searchParams.set("sort", a.dataset.sortValue);
            a.setAttribute("href", url.toString());
        });

        function matches(row) {
            const nameData = row.querySelector(".my-checks-name").dataset;
            if (search) {
                const haystack = [nameData.name, nameData.slug, row.id].join("\n").toLowerCase();
                if (!haystack.includes(search)) return false;
            }

            if (checked.length) {
                const tags = nameData.tags.split(" ");
                if (!checked.every((tag) => tags.includes(tag))) return false;
            }

            return statuses.length === 0 || statusMatch(row, statuses);
        }

        let numVisible = 0;
        hc.$$("#checks-table tr.checks-row").forEach(function (row) {
            const match = matches(row);
            hc.toggle(row, match);
            if (match) numVisible += 1;
        });

        hc.toggle("#checks-table", numVisible > 0);
        hc.toggle("#no-checks", numVisible === 0);
    }

    // User clicks on tags: apply filters
    hc.on("#my-checks-tags .btn", "click", function () {
        this.classList.toggle("checked");
        applyFilters();
    });

    // User changes the search string: apply filters
    hc.on("#search", "input", applyFilters);

    function switchUrlFormat(format) {
        const url = new URL(window.location.href);
        url.searchParams.delete("urls");
        url.searchParams.append("urls", format);
        window.location.href = url.toString();
        return false;
    }

    hc.on("#to-uuid", "click", () => switchUrlFormat("uuid"));
    hc.on("#to-slug", "click", () => switchUrlFormat("slug"));

    function isPaused(code) {
        return rowEl(code, "span.status").classList.contains("ic-paused");
    }

    hc.tooltip(".pause", {
        title: function () {
            if (isPaused(rowCode(this))) {
                return "This check is already paused.";
            }

            return "Pause this check?<br />Click again to confirm.";
        },
        trigger: "manual",
        html: true,
    });

    hc.on(".pause", "click", function () {
        const btn = this;
        const tip = hc.tooltip(btn);
        const code = rowCode(btn);

        // A click on an already paused check. Bootstrap 5 hides a manual tooltip that
        // is shown again while open, so show it only when it is not open yet.
        if (isPaused(code)) {
            if (!btn.hasAttribute("aria-describedby")) tip.show();
            return false;
        }

        // First click: show a confirmation tooltip
        if (!btn.classList.contains("confirm")) {
            btn.classList.add("confirm");
            tip.show();
            return false;
        }

        // Second click: update UI and pause the check
        btn.classList.remove("confirm");
        tip.hide();
        const status = rowEl(code, "span.status");
        const previous = status.className;
        status.className = "status ic-paused";

        hc.post(base + "/checks/" + code + "/pause/").catch(function () {
            // The check was not paused: show its status again
            status.className = previous;
        });

        return false;
    });

    hc.on(".pause", "mouseleave", function () {
        this.classList.remove("confirm");
        hc.tooltip(this).hide();
    });

    // Status icons and sort links. The status icon's class changes as the page
    // refreshes, so the title is computed on every show.
    hc.tooltip("#checks-table span.status, #checks-table a[data-sort-value]", {
        html: true,
        title: function () {
            const cssClasses = this.getAttribute("class");
            if (cssClasses.indexOf("ic-new") > -1)
                return "New. Has never received a ping.";
            if (cssClasses.indexOf("ic-paused") > -1)
                return "Monitoring paused.<br />Ping to resume.";

            if (cssClasses.indexOf("sort-name") > -1)
                return "Sort by name<br />(but failed always first)";

            if (cssClasses.indexOf("sort-last-ping") > -1)
                return "Sort by last ping<br />(but failed always first)";
        },
    });

    // Schedule refresh to run every 3s when tab is visible and user
    // is active, every 60s otherwise
    const lastStatus = {};
    const lastStarted = {};
    const lastPing = {};
    const statusUrl = table ? table.dataset.statusUrl : null;
    function refreshStatus() {
        hc.getJSON(statusUrl, null, { timeout: 2000 }).then(function (data) {
            let statusChanged = false;
            for (const el of data.details) {
                if (lastStatus[el.code] !== el.status) {
                    lastStatus[el.code] = el.status;
                    const statusSpan = rowEl(el.code, "span.status");
                    if (statusSpan) {
                        statusSpan.className = "status ic-" + el.status;
                    }
                    statusChanged = true;
                }

                if (lastStarted[el.code] !== el.started) {
                    lastStarted[el.code] = el.started;
                    const spinner = rowEl(el.code, ".spinner");
                    if (spinner) {
                        spinner.classList.toggle("started", el.started);
                    }
                    statusChanged = true;
                }

                if (lastPing[el.code] !== el.last_ping) {
                    lastPing[el.code] = el.last_ping;
                    const lastPingCell = rowEl(el.code, ".last-ping");
                    if (lastPingCell) {
                        lastPingCell.innerHTML = el.last_ping;
                    }
                }
            }

            // If there were status updates and we have active status filters
            // then we need to reapply filters now:
            if (statusChanged && activeStatusButtons().length) {
                applyFilters();
            }

            hc.$$("#my-checks-tags > .btn").forEach(function (btn) {
                const tag = btn.innerText;
                // A tag that no check carries any more has no entry: leave its button as it is
                const tagData = data.tags[tag];
                if (!tagData) return;

                btn.setAttribute("data-tooltip", tagData[1]);
                const status = tagData[0];
                if (lastStatus[tag] !== status) {
                    btn.classList.remove("up", "grace", "down");
                    btn.classList.add(status);
                    lastStatus[tag] = status;
                }
            });

            if (document.title !== data.title) {
                document.title = data.title;
                hc.setFavicon(data.title.includes("down"));
            }
        }).catch(function () {});
    }

    // Schedule regular status updates:
    if (statusUrl) {
        adaptiveSetInterval(refreshStatus);
    }

    hc.tagSelect("#update-tags-input", hc.$$("#my-checks-tags .btn").map((el) => el.textContent));

    hc.tooltip(".my-checks-url", { title: "Click to copy" });
    hc.on(".my-checks-url", "click", function () {
        if (window.getSelection().toString()) {
            // do nothing, selection not empty
            return;
        }

        hc.copy(this, this.textContent, "Click to copy");
    });

    hc.on("#filters .dropdown-item[data-value]", "click", function () {
        hc.toggle('.filter-btn[data-value="' + this.dataset.value + '"]');
        applyFilters();
    });

    hc.on(".filter-btn", "click", function () {
        hc.hide(this);
        applyFilters();
    });
});
