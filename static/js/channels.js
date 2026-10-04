hc.ready(function() {
    const cm = hc.$("#checks-modal");

    // The URL of the form being loaded, so that a slower earlier load does not
    // replace it
    let loadingUrl = null;
    hc.on(".edit-checks", "click", function() {
        const tip = bootstrap.Tooltip.getInstance(this);
        if (tip) tip.hide();

        // Replace the previous integration's form at once: it carries that
        // integration's code, and saving it would change that integration
        const content = hc.$(".modal-content", cm);
        content.innerHTML = "<div class='modal-body'>Loading&hellip;</div>";
        hc.showModal(cm);

        const url = this.dataset.url;
        loadingUrl = url;
        hc.getText(url).then(function(html) {
            if (url === loadingUrl) content.innerHTML = html;
        }).catch(function() {
            if (url === loadingUrl) content.innerHTML = "<div class='modal-body'>Failed to load.</div>";
        });

        return false;
    });

    function updateNumAssigned() {
        const boxes = hc.$$("input[type=checkbox]", cm);
        const numAssigned = boxes.filter(function(box) { return box.checked; }).length;
        const counter = hc.$("#num-assigned", cm);
        if (counter) counter.textContent = numAssigned;

        const selectAll = hc.$("#select-all", cm);
        if (selectAll) selectAll.disabled = numAssigned === boxes.length;
        const unselectAll = hc.$("#unselect-all", cm);
        if (unselectAll) unselectAll.disabled = numAssigned === 0;
    }

    function setAll(checked) {
        hc.$$("input[type=checkbox]", cm).forEach(function(box) {
            box.checked = checked;
        });
        updateNumAssigned();
    }

    hc.on(cm, "click", "#select-all", function() { setAll(true); });
    hc.on(cm, "click", "#unselect-all", function() { setAll(false); });
    // When any checkbox changes its value, update the "(x of y)" in the title
    hc.on(cm, "change", "input", updateNumAssigned);
    // Let the user click anywhere in the row to toggle the checkbox
    hc.on(cm, "click", "tr", function(event) {
        if (event.target.type !== "checkbox") {
            const box = hc.$("input[type=checkbox]", this);
            if (box) box.click();
        }
    });

    hc.on(".channel-remove", "click", function() {
        const btn = this;
        hc.$("#remove-channel-form").setAttribute("action", btn.dataset.url);
        hc.$$(".remove-channel-kind").forEach(function(el) {
            el.textContent = btn.dataset.kind;
        });
        hc.showModal("#remove-channel-modal");

        return false;
    });

    hc.on(".channel-modal", "shown.bs.modal", function() {
        const input = hc.$(".input-name", this);
        if (input) input.focus();
    });
});
