hc.ready(function() {
    // Show the "Request Body" field only for methods that send a body
    ["down", "up"].forEach(function(kind) {
        const select = document.getElementById("method-" + kind);
        if (!select) return;

        function update() {
            hc.toggle("#body-" + kind + "-group", select.value !== "GET");
        }

        select.addEventListener("change", update);
        update();
    });
});
