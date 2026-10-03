// The small helper the page scripts use where they used jQuery.
// base.html and base_project.html load it right after bootstrap.bundle.min.js, so
// `bootstrap` and `hc` are globals in every page script. Everything here is null-safe:
// a selector that matches nothing is a no-op, as it was with jQuery.
(function() {
    "use strict";

    // Element | Document | Window | selector string | NodeList | array -> array of targets
    function all(target, root) {
        if (!target) return [];
        if (typeof target == "string") {
            return Array.from((root || document).querySelectorAll(target));
        }
        if (target instanceof EventTarget) return [target];
        return Array.from(target);
    }

    function ready(fn) {
        if (document.readyState == "loading") {
            document.addEventListener("DOMContentLoaded", fn);
        } else {
            fn();
        }
    }

    // on(target, "click change", handler) binds directly to every target;
    // on(target, "click", ".child", handler) delegates to children matching the selector,
    // including ones added later. The handler gets (event, element), with `this` set to
    // the bound or the matched element. A handler that returns false prevents the default
    // and stops propagation, as in jQuery. Use mouseover/focusin rather than
    // mouseenter/focus for delegation: those do not bubble.
    function on(target, types, selector, handler) {
        if (typeof selector == "function") {
            handler = selector;
            selector = null;
        }

        all(target).forEach(function(root) {
            types.split(" ").forEach(function(type) {
                root.addEventListener(type, function(event) {
                    var el = root;
                    if (selector) {
                        var start = event.target.closest ? event.target : event.target.parentElement;
                        el = start && start.closest(selector);
                        if (!el || (root.contains && !root.contains(el))) return;
                    }

                    if (handler.call(el, event, el) === false) {
                        event.preventDefault();
                        event.stopPropagation();
                    }
                });
            });
        });
    }

    // The href of #base-url (the navbar's "All Projects" link or the logo) without its
    // trailing slash: SITE_ROOT's path, or "" at the domain root.
    function base() {
        var el = document.getElementById("base-url");
        return el ? el.getAttribute("href").replace(/\/$/, "") : "";
    }

    function csrfToken() {
        var input = document.querySelector("input[name=csrfmiddlewaretoken]");
        if (input) return input.value;

        var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
        return m ? decodeURIComponent(m[1]) : "";
    }

    // A form's successful controls, as jQuery's .serialize(): disabled and unchecked
    // fields are left out.
    function serialize(form) {
        if (typeof form == "string") form = document.querySelector(form);
        return new URLSearchParams(new FormData(form));
    }

    // {a: 1, b: [2, 3]} -> "a=1&b=2&b=3"; URLSearchParams, FormData and forms pass through.
    function toParams(data) {
        if (!data) return new URLSearchParams();
        if (data instanceof URLSearchParams) return data;
        if (data instanceof HTMLFormElement) return serialize(data);
        if (data instanceof FormData) return new URLSearchParams(data);

        var params = new URLSearchParams();
        Object.keys(data).forEach(function(key) {
            var value = data[key];
            if (value === undefined || value === null) return;
            [].concat(value).forEach(function(v) { params.append(key, v); });
        });
        return params;
    }

    function sameOrigin(url) {
        return new URL(url, window.location.href).origin == window.location.origin;
    }

    // fetch() that resolves to the Response for a 2xx status and rejects otherwise, like
    // jQuery's success/error split. opts: method, data (the POST body or the GET query),
    // timeout (ms), signal (an AbortSignal, e.g. to cancel a superseded request), headers.
    // A same-origin request carries X-Requested-With, as jQuery's did (the pause view
    // answers it differently), and a same-origin POST carries X-CSRFToken. A cross-origin
    // request carries neither, so it stays a simple request with no CORS preflight.
    function request(url, opts) {
        opts = opts || {};
        var method = (opts.method || "GET").toUpperCase();
        var headers = Object.assign({}, opts.headers);
        var init = {method: method, headers: headers};

        var params = toParams(opts.data);
        if (method == "GET") {
            var qs = params.toString();
            if (qs) url += (url.indexOf("?") == -1 ? "?" : "&") + qs;
        } else {
            init.body = params;
        }

        if (sameOrigin(url)) {
            headers["X-Requested-With"] = "XMLHttpRequest";
            if (method != "GET") headers["X-CSRFToken"] = csrfToken();
        }

        var signals = [];
        if (opts.timeout) signals.push(AbortSignal.timeout(opts.timeout));
        if (opts.signal) signals.push(opts.signal);
        if (signals.length) init.signal = signals.length == 1 ? signals[0] : AbortSignal.any(signals);

        return fetch(url, init).then(function(response) {
            if (!response.ok) {
                var err = new Error("HTTP " + response.status + " from " + url);
                err.response = response;
                throw err;
            }
            return response;
        });
    }

    function get(url, params, opts) {
        return request(url, Object.assign({}, opts, {method: "GET", data: params}));
    }

    function getText(url, params, opts) {
        return get(url, params, opts).then(function(r) { return r.text(); });
    }

    function getJSON(url, params, opts) {
        return get(url, params, opts).then(function(r) { return r.json(); });
    }

    function post(url, data, opts) {
        return request(url, Object.assign({}, opts, {method: "POST", data: data}));
    }

    // show/hide work on Bootstrap's d-none, and show() also clears an inline
    // style="display: none" and the hidden attribute, so an element can start hidden
    // either way. An element that JS shows and hides must not carry a responsive d-*
    // class (d-md-block and the like): those are !important and override d-none.
    function show(target) {
        all(target).forEach(function(el) {
            el.classList.remove("d-none");
            el.hidden = false;
            if (el.style.display == "none") el.style.display = "";
        });
    }

    function hide(target) {
        all(target).forEach(function(el) {
            el.classList.add("d-none");
        });
    }

    function isHidden(el) {
        return el.hidden || el.classList.contains("d-none") || el.style.display == "none";
    }

    // toggle(target, true) shows, toggle(target, false) hides, toggle(target) flips each.
    function toggle(target, visible) {
        all(target).forEach(function(el) {
            var v = visible === undefined ? isHidden(el) : visible;
            if (v) show(el); else hide(el);
        });
    }

    // jQuery's :visible
    function isVisible(el) {
        return !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    }

    function first(target) {
        return all(target)[0] || null;
    }

    // The bootstrap.Modal of an element or selector, or null when it is not on the page.
    // Options apply only when the instance is first created.
    function modal(target, opts) {
        var el = first(target);
        return el ? bootstrap.Modal.getOrCreateInstance(el, opts) : null;
    }

    function showModal(target, opts) {
        var m = modal(target, opts);
        if (m) m.show();
        return m;
    }

    function hideModal(target) {
        var m = modal(target);
        if (m) m.hide();
        return m;
    }

    // One tooltip per element: tooltip("#x", {title: "..."}) -> the instance of the first
    // match (or null), created on every match.
    function tooltip(target, opts) {
        var instances = all(target).map(function(el) {
            return bootstrap.Tooltip.getOrCreateInstance(el, Object.assign({container: "body"}, opts));
        });
        return instances[0] || null;
    }

    // Delegated tooltips for the children of root that match selector, including rows
    // the page re-renders later. A `title` function is called with the hovered element
    // as `this` and as its argument (so write `function`, not an arrow, to use `this`).
    // Root it on a page element, not document.body, which carries the global delegation
    // below, and leave data-bs-toggle="tooltip" off those children.
    function tooltips(root, selector, opts) {
        var el = first(root);
        if (!el) return null;
        return new bootstrap.Tooltip(el, Object.assign({container: "body"}, opts, {selector: selector}));
    }

    // Show `text` in the element's tooltip now (e.g. "Copied!"); the next time it opens
    // it shows `resting`, by default the element's title attribute, again. A tooltip
    // whose title came from the options needs `resting`, or it keeps saying `text`.
    function flashTooltip(el, text, resting) {
        var tip = bootstrap.Tooltip.getOrCreateInstance(el);
        tip.setContent({".tooltip-inner": text});
        tip.show();
        resting = resting || el.getAttribute("data-bs-original-title");
        if (resting && resting != text) {
            el.addEventListener("hidden.bs.tooltip", function() {
                tip.setContent({".tooltip-inner": resting});
            }, {once: true});
        }
        return tip;
    }

    // Every element with data-bs-toggle="tooltip" and a title gets a tooltip, also when it
    // is added later. Per-element options go in data-bs-* attributes (data-bs-html,
    // data-bs-placement).
    ready(function() {
        new bootstrap.Tooltip(document.body, {
            selector: '[data-bs-toggle="tooltip"]',
            container: "body"
        });
    });

    window.hc = {
        ready: ready,
        $: function(selector, root) { return (root || document).querySelector(selector); },
        $$: function(selector, root) { return all(selector, root); },
        on: on,
        base: base,
        csrfToken: csrfToken,
        serialize: serialize,
        request: request,
        get: get,
        getText: getText,
        getJSON: getJSON,
        post: post,
        show: show,
        hide: hide,
        toggle: toggle,
        isVisible: isVisible,
        modal: modal,
        showModal: showModal,
        hideModal: hideModal,
        tooltip: tooltip,
        tooltips: tooltips,
        flashTooltip: flashTooltip
    };
})();
