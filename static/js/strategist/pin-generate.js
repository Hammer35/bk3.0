// Pin generation page: selection counter, "changed from auto" markers, advanced counter, job polling.
(function () {
    "use strict";
    var form = document.querySelector("[data-gen-form]");
    if (!form) { return; }
    var max = parseInt(form.dataset.maxItems, 10) || 6;
    var items = Array.prototype.slice.call(form.querySelectorAll("[data-gen-item]:not(:disabled)"));
    var all = form.querySelector("[data-gen-all]");
    var count = form.querySelector("[data-gen-count]");
    var limit = form.querySelector("[data-gen-limit]");
    var submit = form.querySelector("[data-gen-submit]");

    function value(el) {
        if (el.type === "checkbox") { return el.checked ? "on" : ""; }
        return el.value;
    }

    function refreshCount() {
        var selected = items.filter(function (el) { return el.checked; }).length;
        if (count) { count.textContent = String(selected); }
        var invalid = selected < 1 || selected > max;
        if (limit) { limit.hidden = selected <= max; }
        if (submit) { submit.disabled = invalid; }
        if (all) { all.checked = items.length > 0 && selected === items.length; }
    }

    function refreshChanged() {
        var changed = 0;
        form.querySelectorAll("[data-gen-field]").forEach(function (field) {
            var input = field.querySelector("input, select, textarea");
            if (!input) { return; }
            var different = value(input) !== (field.dataset.auto || "");
            var badge = field.querySelector("[data-source-badge]");
            var reset = field.querySelector("[data-gen-reset]");
            field.classList.toggle("is-changed", different);
            if (reset) { reset.hidden = !different; }
            if (badge && different) { badge.textContent = badge.dataset.changedLabel || badge.textContent; }
            if (badge && !different) { badge.textContent = badge.dataset.sourceLabel; }
            if (different && field.closest("[data-gen-advanced]")) { changed += 1; }
        });
        var label = form.querySelector("[data-gen-changed]");
        if (label) { label.textContent = changed ? "· " + changed : ""; }
    }

    items.forEach(function (el) { el.addEventListener("change", refreshCount); });
    if (all) {
        all.addEventListener("change", function () {
            items.forEach(function (el, index) { el.checked = all.checked && index < max; });
            refreshCount();
        });
    }
    form.addEventListener("input", refreshChanged);
    form.addEventListener("change", refreshChanged);
    form.querySelectorAll("[data-gen-reset]").forEach(function (button) {
        button.addEventListener("click", function () {
            var field = button.closest("[data-gen-field]");
            var input = field.querySelector("input, select, textarea");
            if (input.type === "checkbox") { input.checked = field.dataset.auto === "on"; } else { input.value = field.dataset.auto || ""; }
            refreshChanged();
        });
    });
    refreshCount();
    refreshChanged();

    // Active jobs report progress without a page reload; a finished job reloads the page once.
    document.querySelectorAll("[data-job-status-url]").forEach(function (card) {
        var labels = {};
        try { labels = JSON.parse(card.dataset.jobLabels || "{}"); } catch (error) { labels = {}; }
        var timer = window.setInterval(function () {
            fetch(card.dataset.jobStatusUrl, { headers: { "X-Requested-With": "XMLHttpRequest" }, credentials: "same-origin" })
                .then(function (response) { return response.ok ? response.json() : null; })
                .then(function (data) {
                    if (!data) { return; }
                    var bar = card.querySelector("[data-job-bar]");
                    var done = data.done + data.failed;
                    if (bar && data.total) { bar.value = Math.min(100, Math.round(done * 100 / data.total)); }
                    var label = card.querySelector("[data-job-label]");
                    if (label) { label.textContent = labels[data.status] || data.label; }
                    if (data.finished) { window.clearInterval(timer); window.setTimeout(function () { window.location.reload(); }, 800); }
                })
                .catch(function () { /* keep polling; the next tick may succeed */ });
        }, 3000);
    });
})();
