# Healio - Centralized Medical Information System

A Django app that connects patients, doctors, pharmacies and laboratories.

| Role | What they can do |
| --- | --- |
| Patient | Find doctors, book / cancel appointments, view prescriptions, tests and medical history |
| Doctor | Manage schedule and profile, see appointments, prescribe medicine and tests, write medical history |
| Pharmacy | Look up a patient's prescriptions and mark them fulfilled |
| Laboratory | See requested tests and mark them completed |

Every page and API endpoint is restricted to the matching role; JSON endpoints enforce CSRF.

## Setup

```bash
python -m venv env
env\Scripts\activate           # Windows
pip install -r requirements.txt

# MySQL: create an empty database, e.g.  CREATE DATABASE cmis CHARACTER SET utf8mb4;
copy .env.example .env         # then edit DB_NAME / DB_PASSWORD / SECRET_KEY
python manage.py migrate
python manage.py seed_demo     # optional demo accounts (development only)
python manage.py runserver
```

Settings are read from environment variables (or a git-ignored `.env` file):
`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DB_NAME`, `DB_PASSWORD`.

> Use a database that is **not** shared with another copy of the project - migrations
> from different versions of the code will conflict.

## Appointments

Doctors set working hours, a specialization and unavailable dates on their profile.
Patients can book 30-minute slots up to 14 days ahead; already-booked and past slots are hidden,
and double booking is prevented.

## AI health assistant (patients)

Patients get an "Ask AI" chat button on every page. Set `OPENAI_API_KEY` (and optionally `OPENAI_MODEL`)
in `.env` to answer with OpenAI; without a key it uses built-in guidance. Severe-symptom messages
(e.g. chest pain) are answered locally with an emergency notice, no patient identifiers are sent to
OpenAI, and the assistant is restricted to health topics only (off-topic or rule-changing requests are
declined locally and by the model's instructions). Each user is limited to 30 messages per 10 minutes.

## Tests

```bash
python manage.py test accounts
```
