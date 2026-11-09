"""AI health assistant used by the patient chat widget.

The assistant gives general guidance only. It never receives patient identifiers, and it falls back to
built-in guidance when no OpenAI key is configured or the API is unavailable.
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 1000
RATE_LIMIT_MESSAGES = 30          # messages ...
RATE_LIMIT_WINDOW_SECONDS = 600   # ... per 10 minutes per user
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

SYSTEM_PROMPT = """You are a careful medical information assistant inside a patient portal in Pakistan.
Your role:
1. Give helpful, general health guidance and explain symptoms in plain language.
2. Say when someone should seek care, and how urgently.
3. Share simple self-care and first-aid information.
4. Always make clear that you cannot diagnose or replace a doctor.

Safety rules:
- For true emergencies (severe chest pain, difficulty breathing, severe bleeding, loss of consciousness,
  stroke signs, severe allergic reaction) say exactly: "This sounds like a medical emergency. Please call 1122 immediately."
- For urgent but non-emergency situations say "You should see a doctor soon".
- Never give prescription-only dosing instructions or tell the user to stop prescribed medicine.
- Be empathetic, concise (under 150 words) and use short bullet points where helpful.
- If the question is not about health, politely say you can only help with health questions."""

EMERGENCY_TERMS = (
    "chest pain", "can't breathe", "cannot breathe", "difficulty breathing", "trouble breathing",
    "short of breath", "unconscious", "passed out", "severe bleeding", "won't stop bleeding",
    "stroke", "seizure", "heart attack", "overdose", "suicid", "anaphyla", "choking",
)

EMERGENCY_REPLY = (
    "**This sounds like a medical emergency. Please call 1122 immediately** or go to the nearest "
    "emergency room.\n\n"
    "• Do not drive yourself if you feel faint or unwell\n"
    "• Stay with someone until help arrives\n\n"
    "I can only offer general information and cannot replace emergency care."
)

NEARBY_TERMS = ("nearby", "near me", "hospital", "pharmacy", "clinic", "laboratory")

NEARBY_REPLY = (
    "To find care close to you, search on a map:\n\n"
    "• **Hospitals**: https://www.google.com/maps/search/hospitals+near+me\n"
    "• **Pharmacies**: https://www.google.com/maps/search/pharmacy+near+me\n"
    "• **Laboratories**: https://www.google.com/maps/search/medical+laboratory+near+me\n\n"
    "You can also book a doctor through **Find a Doctor** in Healio."
)

HEALTH_TERMS = (
    "pain", "ache", "hurt", "sore", "fever", "temperature", "cough", "cold", "flu", "sick", "ill", "unwell",
    "nausea", "vomit", "diarrh", "dizz", "tired", "fatigue", "rash", "itch", "swell", "bleed", "wound", "burn",
    "injur", "fracture", "sprain", "allerg", "asthma", "breath", "chest", "heart", "blood", "pressure", "sugar",
    "diabet", "infection", "stomach", "throat", "headache", "migraine", "back", "knee", "skin", "eye", "ear",
    "tooth", "dental", "pregnan", "symptom", "medicine", "medication", "tablet", "dose", "pill", "vaccine",
    "diet", "sleep", "insomnia", "anxiety", "stress", "depress", "health", "doctor", "pharmac", "hospital",
    "clinic", "lab test", "weak", "numb", "cramp", "constipat", "acid", "urine", "cholesterol",
)

GREETINGS = ("hi", "hello", "hey", "salam", "assalam", "good morning", "good evening", "thanks", "thank you")

OUT_OF_SCOPE_REPLY = (
    "I can only help with **health questions**, so I can't answer that one.\n\n"
    "You can ask me things like:\n"
    "• \"I have a headache and a fever\"\n"
    "• \"When should I see a doctor for a cough?\"\n"
    "• \"What helps with an upset stomach?\""
)

GREETING_REPLY = "Hello! I'm your health assistant. Tell me your symptoms or a health question and I'll do my best to help."

URGENT_MARKERS = ("see a doctor soon", "visit urgent care", "contact your doctor today", "seek medical care promptly")
EMERGENCY_MARKERS = ("call 1122 immediately", "medical emergency", "emergency room immediately")

DISCLAIMER = "\n\n_General information only, not a diagnosis. In an emergency call 1122._"


class RateLimited(Exception):
    pass


def check_rate_limit(user_id):
    key = f"chatbot-rate-{user_id}"
    count = cache.get(key, 0)
    if count >= RATE_LIMIT_MESSAGES:
        raise RateLimited()
    cache.set(key, count + 1, RATE_LIMIT_WINDOW_SECONDS)


def is_emergency(message):
    text = message.lower()
    return any(term in text for term in EMERGENCY_TERMS)


def urgency_from_text(text):
    lowered = text.lower()
    if any(marker in lowered for marker in EMERGENCY_MARKERS):
        return "emergency"
    if any(marker in lowered for marker in URGENT_MARKERS):
        return "urgent"
    return "routine"


def is_health_related(message):
    text = message.lower()
    return any(term in text for term in HEALTH_TERMS)


def is_greeting(message):
    cleaned = message.lower().strip(" !.,?")
    return cleaned in GREETINGS or any(cleaned.startswith(g + " ") for g in GREETINGS) and len(cleaned.split()) <= 3


def fallback_reply(message):
    text = message.lower()
    if is_greeting(message):
        return GREETING_REPLY
    if not is_health_related(message):
        return OUT_OF_SCOPE_REPLY
    if any(w in text for w in ("headache", "head pain", "migraine")):
        body = ("**Headache**\n• Rest in a quiet, dark room\n• Apply a cool compress to your forehead\n"
                "• Drink water\n\n**You should see a doctor soon** if it is sudden and severe, comes with "
                "fever or a stiff neck, or follows a head injury.")
    elif any(w in text for w in ("fever", "temperature")):
        body = ("**Fever**\n• Drink plenty of fluids and rest\n• Dress lightly\n• Check your temperature regularly\n\n"
                "**You should see a doctor soon** if it is above 103°F (39.4°C), lasts more than 3 days, or comes "
                "with breathing difficulty or confusion.")
    elif any(w in text for w in ("cough", "sore throat", "cold", "flu")):
        body = ("**Cold or sore throat**\n• Warm fluids and rest\n• Gargle with warm salt water\n• Avoid smoke\n\n"
                "**You should see a doctor soon** if symptoms last more than a week or you have trouble breathing.")
    elif any(w in text for w in ("stomach", "nausea", "vomit", "diarrhea", "diarrhoea")):
        body = ("**Stomach upset**\n• Sip water or oral rehydration solution\n• Eat light foods when you can\n• Rest\n\n"
                "**You should see a doctor soon** if you cannot keep fluids down, see blood, or pain is severe.")
    else:
        body = ("**General guidance**\n• Rest and stay hydrated\n• Keep track of when symptoms started and how they change\n"
                "• Avoid self-medicating with strong medicines\n\n"
                "If symptoms are getting worse, book an appointment through **Find a Doctor**.")
    return body + DISCLAIMER


def _call_openai(message):
    """Return the assistant's text, or raise on any failure."""
    api_key = getattr(settings, "OPENAI_API_KEY", "") or ""
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    payload = json.dumps({
        "model": getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        "max_tokens": 350,
        "temperature": 0.5,
    }).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_URL, data=payload, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def get_reply(message):
    """Return (text, urgency, source) for a patient's message."""
    message = message.strip()[:MAX_MESSAGE_LENGTH]

    if is_emergency(message):
        return EMERGENCY_REPLY, "emergency", "builtin"

    lowered = message.lower()
    if any(term in lowered for term in NEARBY_TERMS):
        return NEARBY_REPLY, "routine", "builtin"

    if is_greeting(message):
        return GREETING_REPLY, "routine", "builtin"

    try:
        text = _call_openai(message)
        return text + DISCLAIMER, urgency_from_text(text), "ai"
    except Exception as exc:  # network error, bad key, quota, malformed reply ...
        logger.warning("Chatbot falling back to built-in guidance: %s", exc)
        reply = fallback_reply(message)
        return reply, urgency_from_text(reply), "builtin"
