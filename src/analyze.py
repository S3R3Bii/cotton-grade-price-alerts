"""Enumerate fixed authored cases; retain all rules, thresholds and failures."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

from alerts import alert, compare, snapshot

ROOT = Path(__file__).resolve().parents[1]
SHOCKS = ("0", "-1/10", "-1/20", "-1/50", "1/50", "1/20", "1/10")
THRESHOLDS = ("1/100", "1/50", "1/20")
MODES = ("normal", "missing_base", "changed_quality")
RULES = ("grade_blind", "quality_matched")
CASE_FIELDS = [
    "marketing_year",
    "date",
    "market",
    "expansion",
    "shock",
    "identity_mode",
    "rule",
    "threshold",
    "truth_positive",
    "estimated_change",
    "emitted_alert",
    "availability",
    "outcome",
    "value_kind",
]


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def select(rows, phase):
    if phase == "development":
        return [
            r
            for r in rows
            if r["marketing_year"] in {"2022-2023", "2023-2024"}
            and r["market"] in {"Southeast", "North Delta"}
        ]
    return [r for r in rows if r["marketing_year"] == "2024-2025"]


def cases(pair):
    for expansion in (0, 1):
        for shock in SHOCKS:
            for mode in MODES:
                old, new = snapshot(pair, bool(expansion), shock, mode)
                for rule in RULES:
                    estimate, reason = compare(old, new, rule)
                    for threshold in THRESHOLDS:
                        truth = abs(Fraction(shock)) >= Fraction(threshold)
                        decision = alert(estimate, threshold)
                        outcome = (
                            "abstain"
                            if decision is None
                            else (
                                "tp"
                                if truth and decision
                                else "fn" if truth else "fp" if decision else "tn"
                            )
                        )
                        yield dict(
                            zip(
                                CASE_FIELDS,
                                [
                                    pair["marketing_year"],
                                    pair["date"],
                                    pair["market"],
                                    str(expansion),
                                    shock,
                                    mode,
                                    rule,
                                    threshold,
                                    str(int(truth)),
                                    "" if estimate is None else str(estimate),
                                    "" if decision is None else str(int(decision)),
                                    reason,
                                    outcome,
                                    "AUTHORED_CASE_NOT_OBSERVED_ANOMALY",
                                ],
                            )
                        )


def summarize(counts, keys, fields):
    records = []
    for key, totals in sorted(counts.items()):
        row = dict(zip(keys, key))
        row.update({k: totals[k] for k in ["cases", "tp", "fp", "tn", "fn", "abstain"]})
        emitted = totals["cases"] - totals["abstain"]
        pred = totals["tp"] + totals["fp"]
        positive_emitted = totals["tp"] + totals["fn"]
        row.update(
            coverage=str(Fraction(emitted, totals["cases"])),
            conditional_precision=str(Fraction(totals["tp"], pred)) if pred else "",
            conditional_recall_among_emitted=(
                str(Fraction(totals["tp"], positive_emitted))
                if positive_emitted
                else ""
            ),
        )
        records.append(row)
    return records


def run(phase, dest):
    if phase == "held":
        from freeze_proof import verify

        verify()
        frozen = json.loads(
            (ROOT / "DEPENDENCY_FREEZE.json").read_text(encoding="utf-8")
        )
        for name, digest in frozen["sha256"].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, (
                "Frozen dependency changed",
                name,
            )
    rows = list(
        csv.DictReader((ROOT / "data/pairs.csv").open(encoding="utf-8", newline=""))
    )
    selected = select(rows, phase)
    assert selected
    dest.mkdir(parents=True, exist_ok=True)
    keys = [
        "marketing_year",
        "market",
        "rule",
        "threshold",
        "expansion",
        "shock",
        "identity_mode",
    ]
    blockkeys = [
        "marketing_year",
        "month",
        "market",
        "rule",
        "threshold",
        "expansion",
        "identity_mode",
    ]
    counts = defaultdict(lambda: defaultdict(int))
    blockcounts = defaultdict(lambda: defaultdict(int))
    aggregate = defaultdict(lambda: defaultdict(int))
    totals = defaultdict(int)
    with (dest / "cases.csv.gz").open("wb") as raw, gzip.GzipFile(
        filename="", fileobj=raw, mode="wb", mtime=0
    ) as compressed, io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
        writer = csv.DictWriter(text, fieldnames=CASE_FIELDS, lineterminator="\n")
        writer.writeheader()
        for pair in selected:
            for row in cases(pair):
                writer.writerow(row)
                totals["cases"] += 1
                for target, key in [
                    (counts, tuple(row[k] for k in keys)),
                    (
                        blockcounts,
                        tuple(
                            row["date"][:7] if k == "month" else row[k]
                            for k in blockkeys
                        ),
                    ),
                    (
                        aggregate,
                        tuple(
                            row[k]
                            for k in ["rule", "threshold", "expansion", "identity_mode"]
                        ),
                    ),
                ]:
                    target[key]["cases"] += 1
                    target[key][row["outcome"]] += 1
    write_csv(dest / "by_market_case.csv", summarize(counts, keys, None))
    write_csv(dest / "by_month.csv", summarize(blockcounts, blockkeys, None))
    summaries = summarize(
        aggregate, ["rule", "threshold", "expansion", "identity_mode"], None
    )
    write_csv(dest / "summary.csv", summaries)
    premiums = []
    for pair in selected:
        premium = Fraction(pair["added_native"]) / Fraction(pair["base_native"]) - 1
        premiums.append(
            dict(
                marketing_year=pair["marketing_year"],
                date=pair["date"],
                market=pair["market"],
                relative_added_quality_premium=str(premium),
                composition_only_mean_change=str(premium / 2),
            )
        )
    write_csv(dest / "source_premiums.csv", premiums)
    report = dict(
        phase=phase,
        paired_quote_days=len(selected),
        authored_cases=totals["cases"],
        rule_count=2,
        threshold_count=3,
        shock_count=7,
        expansion_states=2,
        identity_modes=3,
        selected_policy=None,
        learned_parameters=None,
        scope="Equally enumerated authored cases, not natural anomaly prevalence or operational precision",
        input_sha256=hashlib.sha256((ROOT / "data/pairs.csv").read_bytes()).hexdigest(),
    )
    (dest / "summary.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["development", "held"], required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    run(args.phase, args.output_dir or ROOT / "results" / args.phase)


if __name__ == "__main__":
    main()
