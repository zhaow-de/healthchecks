hc.ready(function() {
    const markup = '<button type="button" class="btn btn-outline-secondary btn-sm">' +
                 '<span class="ic-clippy"></span>' +
                 '</button>';

    hc.$$(".highlight").forEach(function(el) {
        el.insertAdjacentHTML("beforeend", markup);
        const button = el.lastElementChild;
        const tip = hc.tooltip(button, {title: "Copied", trigger: "manual"});

        button.addEventListener("mouseleave", function() {
            tip.hide();
        });
        button.addEventListener("click", function() {
            navigator.clipboard.writeText(el.innerText).then(
                () => hc.flashTooltip(button, "Copied"),
                () => hc.flashTooltip(button, "Copy failed"),
            );
        });
    });
});
