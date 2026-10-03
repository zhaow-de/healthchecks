hc.ready(function() {
    var cm = hc.$("#checks-modal");

    hc.on(".edit-checks", "click", function() {
        var tip = bootstrap.Tooltip.getInstance(this);
        if (tip) tip.hide();

        hc.showModal(cm);
        hc.getText(this.dataset.url).then(function(html) {
            hc.$(".modal-content", cm).innerHTML = html;
        });

        return false;
    });

    function updateNumAssigned() {
        var boxes = hc.$$("input[type=checkbox]", cm);
        var numAssigned = boxes.filter(function(box) { return box.checked; }).length;
        var counter = hc.$("#num-assigned", cm);
        if (counter) counter.textContent = numAssigned;

        var selectAll = hc.$("#select-all", cm);
        if (selectAll) selectAll.disabled = numAssigned == boxes.length;
        var unselectAll = hc.$("#unselect-all", cm);
        if (unselectAll) unselectAll.disabled = numAssigned == 0;
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
    // Let the user to click anywhere in the row to toggle the checkbox
    hc.on(cm, "click", "tr", function(event) {
        if (event.target.type !== "checkbox") {
            var box = hc.$("input[type=checkbox]", this);
            if (box) box.click();
        }
    });

    hc.on(".channel-remove", "click", function() {
        var btn = this;
        hc.$("#remove-channel-form").setAttribute("action", btn.dataset.url);
        hc.$$(".remove-channel-kind").forEach(function(el) {
            el.textContent = btn.dataset.kind;
        });
        hc.showModal("#remove-channel-modal");

        return false;
    });

    hc.on(".channel-modal", "shown.bs.modal", function() {
        var input = hc.$(".input-name", this);
        if (input) input.focus();
    });
});
