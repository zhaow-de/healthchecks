hc.ready(function () {
    function slugify(text) {
        return text
            .normalize("NFKD")
            .split("")
            .map(ch => ch.charCodeAt(0) < 256 ? ch : "")
            .join("")
            .toLowerCase()
            .replace(/[^\w\s-]/g, "")
            .replace(/[-\s]+/g, "-")
            .replace(/^-+/, "")
            .replace(/-+$/, "");
    }

    hc.$$(".with-slug-suggestions").forEach(function(modal) {
        const nameInput = hc.$("input[name='name']", modal);
        const slugInput = hc.$("input[name='slug']", modal);
        const btn = hc.$(".use-suggested-slug", modal);
        const help = hc.$(".slug-help-block", modal);

        function update() {
            const suggested = slugify(nameInput.value);
            if (suggested) {
                help.innerHTML = `Suggested value: <code>${suggested}</code>`;
            } else {
                help.textContent = "Allowed characters: a-z, 0-9, hyphens, underscores.";
            }

            btn.disabled = !suggested;
        }

        hc.on(nameInput, "input", update);
        hc.on(modal, "shown.bs.modal", update);

        hc.on(btn, "click", function() {
            slugInput.value = slugify(nameInput.value);
        });
    });

});
