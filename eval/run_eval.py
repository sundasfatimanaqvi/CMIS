"""Evaluate a chatbot module on eval/testset.csv.

Run from the project root (next to manage.py):

    python -m eval.run_eval --module eval.baseline_chatbot --name baseline
    python -m eval.run_eval --module accounts.chatbot      --name improved

Default is OFFLINE: the OpenAI call is disabled, so only the local rules and the built-in fallback
are measured (deterministic, free). Add --live to use the configured OPENAI_API_KEY and measure
the whole system (costs a few cents and depends on the model, so run it several times).

IMPORTANT: the labels in testset.csv are drafts. Have a doctor confirm the emergency/answer labels
and a native speaker confirm the Roman Urdu / Urdu wording before you report numbers anywhere.
"""
import argparse
import collections
import csv
import importlib
import json
import logging
import math
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cmis.settings")

import django  # noqa: E402

django.setup()

from django.test.utils import override_settings  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent


def wilson(k, n, z=1.96):
    """95% Wilson score interval for a proportion k/n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


LIVE_PAUSE = 1.0                      # seconds between model calls
RETRY_STATUSES = {429, 500, 502, 503}
MAX_RETRIES = 5
BACKOFF = [2, 4, 8, 16, 32]           # seconds to wait before retry 1..5


class LiveStats:
    def __init__(self):
        self.reached = 0              # messages that reached the model layer
        self.ok = 0                   # calls that returned an answer
        self.retries = 0
        self.errors = collections.Counter()   # error description -> count


def install_live_wrapper(mod, stats):
    """Wrap mod._call_openai: pace calls, retry transient HTTP errors, stop on insufficient_quota.

    get_reply() swallows exceptions and falls back to built-in text, so a quota stop uses SystemExit
    (not an Exception subclass) to end the whole run immediately.
    """
    import time
    import urllib.error

    original = mod._call_openai
    state = {"last": 0.0}

    def wrapped(message):
        stats.reached += 1
        for attempt in range(MAX_RETRIES + 1):
            wait = LIVE_PAUSE - (time.monotonic() - state["last"])
            if wait > 0:
                time.sleep(wait)
            try:
                result = original(message)
                state["last"] = time.monotonic()
                stats.ok += 1
                return result
            except urllib.error.HTTPError as exc:
                state["last"] = time.monotonic()
                try:
                    body = exc.read().decode("utf-8", "replace")
                except Exception:
                    body = ""
                if "insufficient_quota" in body:
                    sys.exit("STOPPED: OpenAI returned insufficient_quota (no credit/quota left on this "
                             "key). Add billing or credit, then re-run. "
                             f"{stats.ok} model answers were received before stopping.")
                if exc.code in RETRY_STATUSES and attempt < MAX_RETRIES:
                    stats.retries += 1
                    time.sleep(BACKOFF[attempt])
                    continue
                stats.errors[f"HTTP {exc.code}"] += 1
                raise
            except Exception as exc:
                state["last"] = time.monotonic()
                stats.errors[type(exc).__name__ + ": " + str(exc)[:80]] += 1
                raise

    mod._call_openai = wrapped


def classify(mod, text, urgency):
    if urgency == "emergency":
        return "emergency"
    if text.startswith(mod.OUT_OF_SCOPE_REPLY):
        return "refuse"
    if text.startswith(mod.GREETING_REPLY):
        return "greeting"
    if text.startswith(mod.NEARBY_REPLY):
        return "nearby"
    return "answer"


def load_cases(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def rate(k, n):
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "rate": (k / n if n else None), "ci95": [lo, hi]}


def summarise(results):
    """results: list of dicts with language, expected, predicted."""
    out = {}
    for lang in ["all", "en", "roman_ur", "ur"]:
        rs = [r for r in results if lang == "all" or r["language"] == lang]
        if not rs:
            continue
        emerg = [r for r in rs if r["expected"] == "emergency"]
        non_emerg = [r for r in rs if r["expected"] != "emergency"]
        refuse = [r for r in rs if r["expected"] == "refuse"]
        answer = [r for r in rs if r["expected"] == "answer"]
        out[lang] = {
            "cases": len(rs),
            "emergency_recall": rate(sum(r["predicted"] == "emergency" for r in emerg), len(emerg)),
            "false_alarm_rate": rate(sum(r["predicted"] == "emergency" for r in non_emerg), len(non_emerg)),
            "offtopic_refusal_rate": rate(sum(r["predicted"] == "refuse" for r in refuse), len(refuse)),
            "false_refusal_rate": rate(sum(r["predicted"] == "refuse" for r in answer), len(answer)),
            "accuracy": rate(sum(r["predicted"] == r["expected"] for r in rs), len(rs)),
        }
    return out


def fmt(x):
    if x["n"] == 0:
        return "n/a"
    return f"{100 * x['rate']:.1f}% ({x['k']}/{x['n']})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", default="accounts.chatbot")
    ap.add_argument("--name", default=None)
    ap.add_argument("--live", action="store_true", help="use the real OpenAI API (needs OPENAI_API_KEY)")
    ap.add_argument("--testset", default=str(HERE / "testset.csv"))
    args = ap.parse_args()
    name = args.name or args.module.replace(".", "_")

    mod = importlib.import_module(args.module)
    cases = load_cases(args.testset)
    live_stats = LiveStats()

    if args.live:
        from django.conf import settings
        if not getattr(settings, "OPENAI_API_KEY", ""):
            sys.exit("--live needs OPENAI_API_KEY in your .env / environment")
        ctx = override_settings()
        install_live_wrapper(mod, live_stats)
    else:
        ctx = override_settings(OPENAI_API_KEY="")

    if not args.live:
        logging.disable(logging.WARNING)  # silence the "falling back to built-in guidance" warnings

    results = []
    with ctx:
        for c in cases:
            text, urgency, source = mod.get_reply(c["text"])
            results.append({
                "id": c["id"], "language": c["language"], "category": c["category"],
                "expected": c["expected"], "predicted": classify(mod, text, urgency),
                "source": source, "input": c["text"],
            })

    summary = summarise(results)
    by_cat = collections.defaultdict(lambda: [0, 0])
    for r in results:
        by_cat[r["category"]][1] += 1
        by_cat[r["category"]][0] += r["predicted"] == r["expected"]

    outdir = HERE / "results"
    outdir.mkdir(exist_ok=True)
    mode = "live" if args.live else "offline"
    import datetime
    import subprocess
    from django.conf import settings
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                cwd=HERE.parent, timeout=10).stdout.strip()
    except Exception:  # git missing - not fatal
        commit = ""
    meta = {  # recorded so a live run can be reproduced / compared later (provider models change)
        "run_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_commit": commit,
        "testset": pathlib.Path(args.testset).name,
        "cases": len(results),
        "answered_by_model": sum(r["source"] == "ai" for r in results),
        "model": getattr(settings, "OPENAI_MODEL", "gpt-4o-mini") if args.live else None,
        "temperature": 0.5 if args.live else None,  # hard-coded in accounts/chatbot.py
    }
    (outdir / f"{name}_{mode}.json").write_text(json.dumps(
        {"module": args.module, "mode": mode, "meta": meta, "summary": summary,
         "by_category": {k: {"correct": v[0], "total": v[1]} for k, v in by_cat.items()}}, indent=2),
        encoding="utf-8")
    with open(outdir / f"{name}_{mode}_failures.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "language", "category", "expected", "predicted", "input"])
        for r in results:
            if r["predicted"] != r["expected"]:
                w.writerow([r["id"], r["language"], r["category"], r["expected"], r["predicted"], r["input"]])

    print(f"\n{name} ({mode}) - {len(results)} cases\n")
    if args.live:
        answered = sum(r["source"] == "ai" for r in results)
        print(f"Answered by the model: {answered}/{len(results)}")
        print(f"Messages that reached the model: {live_stats.reached} "
              f"(successful calls {live_stats.ok}, retries {live_stats.retries})")
        for err, n in live_stats.errors.most_common():
            print(f"  error x{n}: {err}")
        print()
    print("| Metric | All | English | Roman Urdu | Urdu |")
    print("|---|---|---|---|---|")
    for key, label in [("emergency_recall", "Emergency recall"), ("false_alarm_rate", "False-alarm rate"),
                       ("offtopic_refusal_rate", "Off-topic refused"), ("false_refusal_rate", "Health question wrongly refused"),
                       ("accuracy", "Overall accuracy")]:
        row = [fmt(summary[l][key]) if l in summary else "-" for l in ["all", "en", "roman_ur", "ur"]]
        print(f"| {label} | " + " | ".join(row) + " |")
    print("\nBy category (correct/total):")
    for k, v in sorted(by_cat.items()):
        print(f"  {k:22s} {v[0]}/{v[1]}")


if __name__ == "__main__":
    main()
