/* Healio shared front-end helpers */
(function () {
    "use strict";

    function getCookie(name) {
        var match = document.cookie.split("; ").find(function (row) { return row.indexOf(name + "=") === 0; });
        return match ? decodeURIComponent(match.split("=")[1]) : "";
    }

    function csrfToken() {
        var input = document.querySelector("input[name=csrfmiddlewaretoken]");
        return input ? input.value : getCookie("csrftoken");
    }

    /** Show a Bootstrap toast. type: success | danger | info */
    function toast(message, type) {
        var holder = document.getElementById("hl-toasts");
        if (!holder || !window.bootstrap) { return; }
        var el = document.createElement("div");
        el.className = "toast align-items-center text-bg-" + (type || "info") + " border-0";
        el.setAttribute("role", type === "danger" ? "alert" : "status");
        el.innerHTML = '<div class="d-flex"><div class="toast-body"></div>' +
            '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button></div>';
        el.querySelector(".toast-body").textContent = message;
        holder.appendChild(el);
        var t = new bootstrap.Toast(el, { delay: 3500 });
        el.addEventListener("hidden.bs.toast", function () { el.remove(); });
        t.show();
    }

    /** POST (JSON body optional) with CSRF; resolves with parsed JSON, also for JSON error responses. */
    function postJSON(url, body) {
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken(), "Accept": "application/json" },
            body: JSON.stringify(body || {})
        }).then(function (response) {
            return response.json().catch(function () {
                return { success: false, error: "Unexpected server response (" + response.status + ")." };
            });
        });
    }

    /** Wire a form to postJSON; toasts the result and reloads on success. */
    function ajaxForm(formId, url, buildBody) {
        var form = document.getElementById(formId);
        if (!form) { return; }
        form.addEventListener("submit", function (event) {
            event.preventDefault();
            if (!form.reportValidity()) { return; }
            var button = form.querySelector("[type=submit]");
            if (button) { button.disabled = true; }
            postJSON(url, buildBody(form)).then(function (data) {
                if (data.success) {
                    toast(data.message || "Saved.", "success");
                    setTimeout(function () { window.location.reload(); }, 700);
                } else {
                    toast(data.error || "Something went wrong.", "danger");
                    if (button) { button.disabled = false; }
                }
            }).catch(function () {
                toast("Network error. Please try again.", "danger");
                if (button) { button.disabled = false; }
            });
        });
    }

    // Auto-dismiss flash messages after a few seconds
    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll(".hl-messages .alert").forEach(function (alertEl) {
            setTimeout(function () {
                if (window.bootstrap) { bootstrap.Alert.getOrCreateInstance(alertEl).close(); }
            }, 6000);
        });
    });

    window.Healio = { csrfToken: csrfToken, toast: toast, postJSON: postJSON, ajaxForm: ajaxForm };
})();
