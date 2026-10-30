"""Recompute every authored case and aggregate without analysis/helper imports."""

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def summary(expected, fields):
    rows = []
    for key, c in sorted(expected.items()):
        row = dict(zip(fields, key))
        row.update({k: str(c[k]) for k in ["cases", "tp", "fp", "tn", "fn", "abstain"]})
        emitted = c["cases"] - c["abstain"]
        den = c["tp"] + c["fp"]
        positive = c["tp"] + c["fn"]
        row.update(
            coverage=str(Fraction(emitted, c["cases"])),
            conditional_precision="" if den == 0 else str(Fraction(c["tp"], den)),
            conditional_recall_among_emitted=(
                "" if positive == 0 else str(Fraction(c["tp"], positive))
            ),
        )
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["development", "held"], required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    dest = args.output_dir or ROOT / "results" / args.phase
    all_pairs = list(
        csv.DictReader((ROOT / "data/pairs.csv").open(encoding="utf-8", newline=""))
    )
    if args.phase == "development":
        pairs = [
            r
            for r in all_pairs
            if r["marketing_year"] != "2024-2025"
            and r["market"] in {"Southeast", "North Delta"}
        ]
    else:
        pairs = [r for r in all_pairs if r["marketing_year"] == "2024-2025"]
    assert pairs
    aggregate = defaultdict(Counter)
    detail = defaultdict(Counter)
    blocks = defaultdict(Counter)
    premium_rows = []
    checks = 0
    case_count = 0
    fields = [
        "marketing_year",
        "market",
        "rule",
        "threshold",
        "expansion",
        "shock",
        "identity_mode",
    ]
    blockfields = [
        "marketing_year",
        "month",
        "market",
        "rule",
        "threshold",
        "expansion",
        "identity_mode",
    ]
    aggfields = ["rule", "threshold", "expansion", "identity_mode"]
    with gzip.open(dest / "cases.csv.gz", "rt", encoding="utf-8", newline="") as stream:
        observed = iter(csv.DictReader(stream))
        for pair in pairs:
            b = Fraction(pair["base_native"])
            h = Fraction(pair["added_native"])
            premium = h / b - 1
            premium_rows.append(
                dict(
                    marketing_year=pair["marketing_year"],
                    date=pair["date"],
                    market=pair["market"],
                    relative_added_quality_premium=str(premium),
                    composition_only_mean_change=str(premium / 2),
                )
            )
            for expansion in ["0", "1"]:
                for shock in ["0", "-1/10", "-1/20", "-1/50", "1/50", "1/20", "1/10"]:
                    s = Fraction(shock)
                    for mode in ["normal", "missing_base", "changed_quality"]:
                        for rule in ["grade_blind", "quality_matched"]:
                            estimate = None
                            reason = "available"
                            if rule == "quality_matched":
                                if mode == "normal":
                                    estimate = s
                                else:
                                    reason = "quality_unavailable"
                            elif mode == "missing_base":
                                if expansion == "1":
                                    estimate = h * (1 + s) / b - 1
                                else:
                                    reason = "empty_snapshot"
                            else:
                                estimate = ((b + h) / 2 if expansion == "1" else b) * (
                                    1 + s
                                ) / b - 1
                            for threshold in ["1/100", "1/50", "1/20"]:
                                truth = abs(s) >= Fraction(threshold)
                                decision = (
                                    None
                                    if estimate is None
                                    else abs(estimate) >= Fraction(threshold)
                                )
                                label = (
                                    "abstain"
                                    if decision is None
                                    else (
                                        "tp"
                                        if truth and decision
                                        else (
                                            "fn"
                                            if truth
                                            else "fp" if decision else "tn"
                                        )
                                    )
                                )
                                expected = {
                                    k: pair[k]
                                    for k in ["marketing_year", "date", "market"]
                                }
                                expected.update(
                                    expansion=expansion,
                                    shock=shock,
                                    identity_mode=mode,
                                    rule=rule,
                                    threshold=threshold,
                                    truth_positive=str(int(truth)),
                                    estimated_change=(
                                        "" if estimate is None else str(estimate)
                                    ),
                                    emitted_alert=(
                                        "" if decision is None else str(int(decision))
                                    ),
                                    availability=reason,
                                    outcome=label,
                                    value_kind="AUTHORED_CASE_NOT_OBSERVED_ANOMALY",
                                )
                                row = next(observed)
                                assert row == expected, (
                                    case_count,
                                    pair["date"],
                                    pair["market"],
                                    mode,
                                    rule,
                                    threshold,
                                )
                                checks += len(expected)
                                case_count += 1
                                for target, key in [
                                    (aggregate, tuple(expected[k] for k in aggfields)),
                                    (detail, tuple(expected[k] for k in fields)),
                                    (
                                        blocks,
                                        tuple(
                                            (
                                                expected["date"][:7]
                                                if k == "month"
                                                else expected[k]
                                            )
                                            for k in blockfields
                                        ),
                                    ),
                                ]:
                                    target[key]["cases"] += 1
                                    target[key][label] += 1
        assert next(observed, None) is None
        checks += 1
    for filename, expected in [
        ("summary.csv", summary(aggregate, aggfields)),
        ("by_market_case.csv", summary(detail, fields)),
        ("by_month.csv", summary(blocks, blockfields)),
        ("source_premiums.csv", premium_rows),
    ]:
        actual = list(
            csv.DictReader((dest / filename).open(encoding="utf-8", newline=""))
        )
        assert actual == expected, filename
        checks += sum(len(r) for r in expected)
    report = json.loads((dest / "summary.json").read_text(encoding="utf-8"))
    assert (
        report["paired_quote_days"] == len(pairs)
        and report["authored_cases"] == case_count == len(pairs) * 252
        and report["selected_policy"] is None
        and report["learned_parameters"] is None
    )
    checks += 5
    result = dict(
        status="pass",
        phase=args.phase,
        checks=checks,
        case_rows=case_count,
        source_pairs=len(pairs),
        method="Independent exact Fraction formulas and full-grid enumeration; no analysis/helper imports",
        sha256={
            str(p.relative_to(dest)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(dest.iterdir())
            if p.name != "verification.json"
        },
    )
    (dest / "verification.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
