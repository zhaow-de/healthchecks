hc.ready(function() {
    const base = hc.base();
    const input = document.getElementById("docs-search");
    const results = document.getElementById("search-results");
    const nav = document.getElementById("docs-nav");

    hc.on(input, "input focus", function() {
        const q = this.value;
        if (q.length < 3) {
            results.classList.remove("on");
            nav.classList.remove("off");
            return
        }

        hc.getText(base + "/docs/search/", {q: q}).then(function(data) {
            if (q !== input.value) {
                return;  // ignore stale results
            }

            results.innerHTML = data;
            results.classList.add("on");
            nav.classList.add("off");
        }).catch(function() {});
    });
});
