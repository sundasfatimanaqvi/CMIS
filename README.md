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

## Dashboards and themes

Patient, doctor, pharmacy and laboratory dashboards show summary tiles built from live data; the doctor
dashboard adds a 7-day appointments chart and today's timeline. A light/dark theme toggle in the navbar
remembers your choice (and follows the system setting on first visit). Times use the `Asia/Karachi` time zone.

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

> **Research prototype - not medical advice.** The assistant gives general health information only and is
> not a substitute for a doctor. In an emergency contact local emergency services (Pakistan: Rescue 1122).

## Evaluating the assistant

`eval/` contains a small harness that scores a chatbot module on labelled messages in English, Roman Urdu
and Urdu (expected outcome: `emergency`, `answer`, `refuse` or `nearby`). Each result file stores the
model name, temperature, date, git commit and test-set name so runs can be compared later.

```bash
python -m eval.run_eval --module eval.baseline_chatbot --name baseline                        # offline, free
python -m eval.run_eval --module accounts.chatbot --name improved                             # offline
python -m eval.run_eval --module accounts.chatbot --name improved --live                      # real OpenAI call
python -m eval.run_eval --module accounts.chatbot --name improved_heldout --testset eval/heldout.csv
python eval/summarize_results.py                                                              # rebuild eval/results/summary.txt
```

Test sets: `testset.csv` (165, used while developing), `heldout.csv` (39), `selfharm_indirect.csv` (42),
and `heldout_v2_to_label.csv` (36 new cases, **unlabelled** - for a clinician and a native speaker to label
and then used once, untouched, for the final numbers). See `eval/results/summary.txt` for current results.

## Limitations (read before citing any number)

- **Labels are developer drafts**, not clinician-confirmed; Urdu / Roman Urdu wording is not native-speaker reviewed.
- **The main set (165) was used to tune the rules**, so its ~100% is optimistic. Only a held-out set that
  was never used for tuning is a fair estimate, and the current ones are small (e.g. 3 Urdu emergency cases).
- **The baseline is an earlier version of this project**, not an independent system.
- In the improved system most messages are decided by local safety rules; the language model answers only
  a minority of them, so results describe the rules + model combination, not the model alone.
- Self-harm detection is deliberately cautious and over-refuses some harmless "live / jeena" questions
  (e.g. "how long can a person live without food").
- Live results depend on the provider's model version at the time of the run; repeated runs with identical
  output are not independent evidence.
- No real users or clinical setting have been studied; ethics approval would be needed before that.
