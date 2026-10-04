// The checks that a read-only API key can see, as the API returns them
async function loadChecks(key) {
    const r = await fetch(document.body.dataset.checksUrl, {headers: {"X-Api-Key": key}});
    if (!r.ok) {
        throw new Error("HTTP " + r.status);
    }
    return r.json();
}

function duration(v) {
    if (v < 60) { // v is seconds
        return v + " sec";
    }

    v = Math.floor(v / 60); // v is now minutes
    if (v < 60) {
        return v + " min";
    }

    v = Math.floor(v / 60); // v is now hours
    if (v < 24) {
        return v + " h";
    }

    v = Math.floor(v / 24); // v is now days
    return v + " day" + (v === 1 ? "" : "s");
}

function timeSince(date) {
    const v = Math.floor((new Date() - date) / 1000);
    return duration(v);
}

const template = document.getElementById("check-template");
async function updatePanel(node) {
    let doc;
    try {
        doc = await loadChecks(node.dataset.readonlyKey);
    } catch {
        // A wrong key or a failed request: keep the tiles shown so far
        return;
    }

    const tag = "TAG_" + node.dataset.readonlyKey.slice(0, 6);

    // Sort returned checks by name:
    const sorted = doc.checks.sort(function(a, b) {
        return a.name.localeCompare(b.name)
    });

    const fragment = document.createDocumentFragment();
    sorted.forEach(function(item) {
        const div = template.content.firstElementChild.cloneNode(true);
        div.setAttribute("class", tag + " status-" + item.status + (item.started ? " status-started" : ""));
        div.querySelector(".name").textContent = item.name || "unnamed";
        if (item.last_ping) {
            div.querySelector(".lp").textContent = timeSince(Date.parse(item.last_ping)) + " ago";
        }
        if (item.last_duration) {
            div.querySelector(".ld span").textContent = duration(item.last_duration);
        } else {
            div.querySelector(".ld").textContent = "";
        }
        fragment.appendChild(div);
    });

    document.querySelectorAll('.' + tag).forEach(function(element) {
        element.remove();
    });

    node.parentNode.insertBefore(fragment, node.nextSibling);
}

if (window.location.hash) {
    let panel;

    const pairs = window.location.hash.slice(1).split("&");
    for (const pair of pairs) {
        if (!pair) {
            continue;
        }

        if (pair.indexOf("theme=") !== -1) {
            document.body.setAttribute("class", pair.replace("=", "-"));
            continue;
        }

        const parts = pair.split("=");
        const h1 = document.createElement("H1");
        h1.dataset.readonlyKey = parts[0];
        if (parts[1]) {
            h1.innerText = decodeURIComponent(parts[1]);
        }

        if (!panel) {
            panel = document.getElementById("panel");
            panel.innerHTML = "";
        }
        panel.appendChild(h1);
    }
}
document.querySelectorAll("h1").forEach(updatePanel);
setInterval(function() {
    document.querySelectorAll("h1").forEach(updatePanel);
}, 5000);
