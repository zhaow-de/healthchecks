hc.ready(function() {
    var timeout = null;
    function refreshMenu() {
        if (timeout) return;

        timeout = setTimeout(function() {
            timeout = null
        }, 3000);

        hc.getText(hc.base() + "/projects/menu/", null, {timeout: 2000}).then(function(data) {
            hc.$$("#project-menu li.project-item").forEach(function(el) { el.remove(); });
            hc.$("#projects-divider").insertAdjacentHTML("afterend", data);
        }).catch(function() {});
    }

    hc.on("#project-menu", "mouseenter", refreshMenu);
    hc.on("#project-menu > .dropdown", "show.bs.dropdown", refreshMenu);
});
