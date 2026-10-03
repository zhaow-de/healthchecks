hc.ready(function () {
    hc.showModal("#key-created-modal");

    hc.on(".member-remove", "click", function () {
        hc.$("#rtm-email").textContent = this.dataset.email;
        hc.$("#remove-team-member-email").value = this.dataset.email;
        hc.showModal("#remove-team-member-modal");

        return false;
    });

    hc.on("#invite-team-member-modal", "shown.bs.modal", function () {
        hc.$("#itm-email").focus();
    });

    hc.on("#set-project-name-modal", "shown.bs.modal", function () {
        hc.$("#project-name").focus();
    });

    hc.on(".add-to-team", "click", function () {
        hc.$("#itm-email").value = this.dataset.email;
        hc.showModal("#invite-team-member-modal");
        return false;
    });

    // Enable the submit button in transfer form when user selects
    // the target owner:
    hc.on("#new-owner", "change", function () {
        hc.$("#transfer-confirm").disabled = !this.value;
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
