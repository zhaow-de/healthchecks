hc.ready(function () {
    hc.showModal("#key-created-modal");

    hc.on("#set-project-name-modal", "shown.bs.modal", function () {
        hc.$("#project-name").focus();
    });

    hc.on("a[data-revoke-key]", "click", function () {
        hc.$("#revoke-key-type").value = this.dataset.revokeKey;
        var name = this.dataset.name;
        hc.$$("#revoke-key-modal .name").forEach(function (el) {
            el.textContent = name;
        });
        hc.showModal("#revoke-key-modal");
        return false;
    });

    hc.on("a[data-create-key]", "click", function () {
        hc.$("#create-key-type").value = this.dataset.createKey;
        hc.$("#create-key-form").submit();
        return false;
    });

    hc.tooltip("code[data-plaintext]", {"title": "Click to reveal"});
    hc.on("code[data-plaintext]", "click", function () {
        var tip = bootstrap.Tooltip.getInstance(this);
        if (tip) {
            tip.dispose();
        }
        this.textContent = this.dataset.plaintext;
    });


});
