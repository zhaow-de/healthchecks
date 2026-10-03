hc.ready(function() {
    var base = hc.base();
    var input = document.getElementById("docs-search");
    var results = document.getElementById("search-results");
    var nav = document.getElementById("docs-nav");

    hc.on(input, "keyup focus", function() {
        var q = this.value;
        if (q.length < 3) {
            results.classList.remove("on");
            nav.classList.remove("off");
            return
        }

        hc.getText(base + "/docs/search/", {q: q}).then(function(data) {
            if (q != input.value) {
                return;  // ignore stale results
            }

            results.innerHTML = data;
            results.classList.add("on");
            nav.classList.add("off");
        }).catch(function() {});
    });
});
