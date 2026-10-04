hc.ready(function () {
    hc.on("#add-project-modal", "shown.bs.modal", function () {
        hc.$("#add-project-name").focus();
    });
});
