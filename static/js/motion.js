/* Healio motion: scroll reveal + count-up numbers. Safe no-op without IntersectionObserver / with reduced motion. */
(function () {
    "use strict";
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || !("IntersectionObserver" in window)) { return; }

    document.documentElement.classList.add("js-motion");

    function ready(fn) {
        if (document.readyState !== "loading") { fn(); } else { document.addEventListener("DOMContentLoaded", fn); }
    }

    function countUp(el) {
        var target = parseInt(el.textContent, 10);
        if (isNaN(target) || target <= 0 || String(target) !== el.textContent.trim()) { return; }
        var start = null, duration = 900;
        el.textContent = "0";
        function step(ts) {
            if (start === null) { start = ts; }
            var p = Math.min((ts - start) / duration, 1);
            el.textContent = String(Math.round(target * (1 - Math.pow(1 - p, 3))));
            if (p < 1) { requestAnimationFrame(step); } else { el.textContent = String(target); }
        }
        requestAnimationFrame(step);
    }

    ready(function () {
        var groups = [
            ".hl-step", ".hl-feature", ".hl-benefit", ".hl-doctor-card", ".hl-cta", ".hl-cta-band",
            ".hl-stat", ".hl-section-title", ".hl-section-sub", ".hl-card:not(.hl-doctor-card)"
        ];
        var seen = new Set();
        groups.forEach(function (selector) {
            document.querySelectorAll(selector).forEach(function (node, index) {
                if (seen.has(node)) { return; }
                seen.add(node);
                node.setAttribute("data-reveal", "");
                node.style.setProperty("--reveal-delay", Math.min(index, 6) * 80 + "ms");
            });
        });

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) { return; }
                entry.target.classList.add("is-visible");
                entry.target.querySelectorAll(".value").forEach(countUp);
                if (entry.target.classList.contains("value")) { countUp(entry.target); }
                observer.unobserve(entry.target);
                (function (node) {
                    // Hand control back to the element's own hover styles once the reveal has played.
                    setTimeout(function () {
                        node.removeAttribute("data-reveal");
                        node.classList.remove("is-visible");
                        node.style.removeProperty("--reveal-delay");
                    }, 1200);
                })(entry.target);
            });
        }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });

        seen.forEach(function (node) { observer.observe(node); });
    });
})();
