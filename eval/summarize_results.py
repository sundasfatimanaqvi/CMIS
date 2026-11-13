"""Regenerate eval/results/summary.txt from every *.json / *_failures.csv in eval/results.

Usage:  python eval/summarize_results.py
Output is UTF-8 so Urdu test messages are preserved.
"""
import csv
import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
OUT = RESULTS / "summary.txt"

METRICS = [
    ("Urdu emergency recall", "ur", "emergency_recall"),
    ("Roman Urdu emergency recall", "roman_ur", "emergency_recall"),
    ("English emergency recall", "en", "emergency_recall"),
    ("False alarms", "all", "false_alarm_rate"),
    ("Health wrongly refused", "all", "false_refusal_rate"),
    ("Off-topic refused", "all", "offtopic_refusal_rate"),
]


def ci(m):
    c = m["ci95"]
    if isinstance(c, str):
        c = c.split()
    lo, hi = float(c[0]), float(c[1])
    return f"{lo * 100:.1f}-{hi * 100:.1f}%"


def frac(m):
    return f"{m['k']}/{m['n']} ({m['rate'] * 100:.1f}%)"


def load_runs():
    runs = []
    for p in sorted(RESULTS.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        stem = p.stem
        # <variant>[_<set>]_<mode>
        mode = d.get("mode", stem.rsplit("_", 1)[-1])
        name = stem[: -(len(mode) + 1)] if stem.endswith("_" + mode) else stem
        variant = "baseline" if name.startswith("baseline") else "improved"
        if "heldout" in name:
            group = "held-out"
        elif "selfharm_indirect" in name:
            group = "selfharm-indirect"
        elif "testset" in name:
            group = "main"
        elif "run" in name:
            group = "main"
        else:
            group = "main"
        fails = []
        fp = RESULTS / f"{stem}_failures.csv"
        if fp.exists():
            with fp.open(encoding="utf-8-sig", newline="") as f:
                fails = list(csv.DictReader(f))
        runs.append(dict(stem=stem, name=name, variant=variant, group=group,
                         mode=mode, data=d, fails=fails))
    return runs


def run_line(r):
    a = r["data"]["summary"]["all"]
    acc = a["accuracy"]
    return (f"- {r['name']} [{r['group']}]: {a['cases']} cases | correct "
            f"{acc['k']}/{acc['n']} = {acc['rate'] * 100:.1f}% (95% CI {ci(acc)})")


def comparison(runs, group, mode, improved_name):
    imp = next((r for r in runs if r["name"] == improved_name and r["mode"] == mode), None)
    base_name = improved_name.replace("improved", "baseline")
    base = next((r for r in runs if r["name"] == base_name and r["mode"] == mode), None)
    if not imp or not base:
        return []
    n = imp["data"]["summary"]["all"]["cases"]
    out = [f"{group} ({n}, {mode})"]
    for label, lang, key in METRICS:
        si, sb = imp["data"]["summary"], base["data"]["summary"]
        if lang in si and lang in sb and si[lang][key]["n"]:
            out.append(f"  {label}: improved {frac(si[lang][key])} | baseline {frac(sb[lang][key])}")
    return out


def main():
    runs = load_runs()
    live = [r for r in runs if r["mode"] == "live"]
    offline = [r for r in runs if r["mode"] == "offline"]
    order = lambda r: (r["group"] != "main", r["group"], r["variant"] != "improved", r["name"])
    L = ["EVALUATION SUMMARY (from eval/results/*.json; live and offline runs)", ""]

    L.append("1) Per run: cases | overall correct (95% Wilson interval)")
    L.append("Live (real model + safety layer)")
    L += [run_line(r) for r in sorted(live, key=order)]
    L.append("Offline (built-in rules only, no API)")
    L += [run_line(r) for r in sorted(offline, key=order)]
    L.append("")

    L.append("2) Improved vs baseline")
    L += comparison(runs, "Main set", "live", "improved")
    L += comparison(runs, "Held-out", "live", "improved_heldout")
    L += comparison(runs, "Self-harm indirect phrasings", "offline", "improved_selfharm_indirect")
    L += comparison(runs, "Main set", "offline", "improved")
    L += comparison(runs, "Held-out", "offline", "improved_heldout")
    L.append("")

    L.append("3) Per-category correct (improved vs baseline, selfharm_indirect set)")
    ib = {r["variant"]: r for r in offline if r["group"] == "selfharm-indirect"}
    for cat in sorted({c for r in ib.values() for c in r["data"].get("by_category", {})}):
        parts = []
        for v in ("improved", "baseline"):
            if v in ib:
                c = ib[v]["data"]["by_category"].get(cat)
                if c:
                    parts.append(f"{v} {c['correct']}/{c['total']}")
        L.append(f"  {cat}: " + " | ".join(parts))
    L.append("")

    L.append("4) Every failing case (id | message | expected | got)")
    for r in sorted(runs, key=lambda r: (r["mode"], *order(r))):
        L.append(f"{r['name']} [{r['group']}, {r['mode']}]: {len(r['fails'])} failure(s)")
        for f in r["fails"]:
            L.append(f"  {f['id']} | {f['input']} | expected {f['expected']} | got {f['predicted']}")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
