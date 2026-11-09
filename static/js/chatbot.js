/* Healio AI health assistant widget (patients only). Depends on healio.js. */
(function () {
    "use strict";

    var state = { url: "", open: false, busy: false, started: false };
    var el = {};

    var WELCOME = "Hello! I'm your AI health assistant. Tell me your symptoms and I'll share general guidance " +
        "and when to see a doctor. What are you experiencing?";

    /** Escape HTML first, then apply a small, safe subset of markdown (**bold**, bullets, links, line breaks). */
    function format(text) {
        var safe = String(text)
            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        safe = safe
            .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
            .replace(/(^|\s)_(.+?)_(?=\s|$)/g, "$1<em>$2</em>")
            .replace(/(https:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>')
            .replace(/\n/g, "<br>");
        return safe;
    }

    function addMessage(text, who, extraClass) {
        var wrap = document.createElement("div");
        wrap.className = "hl-msg hl-msg-" + who + (extraClass ? " " + extraClass : "");
        var bubble = document.createElement("div");
        bubble.className = "hl-msg-bubble";
        bubble.innerHTML = format(text);
        wrap.appendChild(bubble);
        el.messages.appendChild(wrap);
        el.messages.scrollTop = el.messages.scrollHeight;
        return wrap;
    }

    function setBusy(busy) {
        state.busy = busy;
        el.send.disabled = busy;
        var existing = document.getElementById("chatTyping");
        if (busy && !existing) {
            var typing = addMessage("", "bot");
            typing.id = "chatTyping";
            typing.firstChild.innerHTML = '<span class="hl-typing"><i></i><i></i><i></i></span>';
        } else if (!busy && existing) {
            existing.remove();
        }
    }

    function send(text) {
        text = (text || "").trim();
        if (!text || state.busy) { return; }
        addMessage(text, "user");
        el.input.value = "";
        el.chips.hidden = true;
        setBusy(true);

        Healio.postJSON(state.url, { message: text }).then(function (data) {
            setBusy(false);
            addMessage(data.response || "Sorry, something went wrong. Please try again.", "bot",
                data.urgency === "emergency" ? "hl-msg-emergency" : (data.urgency === "urgent" ? "hl-msg-urgent" : ""));
            if (data.urgency === "emergency") {
                addMessage("**Emergency?** Call **1122** now. Do not wait for a reply here.", "bot", "hl-msg-emergency");
            }
        }).catch(function () {
            setBusy(false);
            addMessage("I'm having trouble connecting. Please try again, or contact your doctor if it is urgent.", "bot");
        });
    }

    function toggle(open) {
        state.open = typeof open === "boolean" ? open : !state.open;
        el.win.hidden = !state.open;
        el.toggle.setAttribute("aria-expanded", state.open ? "true" : "false");
        el.toggle.classList.toggle("is-open", state.open);
        if (state.open) {
            if (!state.started) { addMessage(WELCOME, "bot"); state.started = true; }
            el.input.focus();
        } else {
            el.toggle.focus();
        }
    }

    function init(options) {
        el.toggle = document.getElementById("chatToggle");
        el.win = document.getElementById("chatWindow");
        if (!el.toggle || !el.win) { return; }
        state.url = options.url;
        el.messages = document.getElementById("chatMessages");
        el.input = document.getElementById("chatInput");
        el.send = document.getElementById("chatSend");
        el.chips = document.getElementById("chatChips");

        el.toggle.addEventListener("click", function () { toggle(); });
        document.getElementById("chatClose").addEventListener("click", function () { toggle(false); });
        document.getElementById("chatForm").addEventListener("submit", function (event) {
            event.preventDefault();
            send(el.input.value);
        });
        el.chips.querySelectorAll("button").forEach(function (chip) {
            chip.addEventListener("click", function () { send(chip.dataset.prompt); });
        });
        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && state.open) { toggle(false); }
        });
    }

    window.Healio = window.Healio || {};
    window.Healio.chatbot = { init: init };
})();
