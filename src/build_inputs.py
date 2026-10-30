"""Retain every paired-key decision before enumerating authored alert cases."""

import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKETS = (
    "Southeast",
    "North Delta",
    "South Delta",
    "East TX-OK",
    "West Texas",
    "Desert SW",
    "SJ Valley",
)


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def qualify(rows):
    groups = defaultdict(list)
    dates = defaultdict(set)
    reasons = Counter()
    for row in rows:
        reasons[row["reason"]] += 1
        if row["reason"] != "source_eligible":
            continue
        key = (row["marketing_year"], row["date"], row["market"], row["grade"])
        groups[key].append(row)
        dates[row["marketing_year"]].add(row["date"])
    quotes = {}
    key_rows = []
    for key, copies in sorted(groups.items()):
        signatures = {
            (
                r["price_native"],
                r["difference_native"],
                r["type"],
                r["color"],
                r["leaf"],
                r["staple"],
                r["unit"],
                r["other_quality_convention"],
            )
            for r in copies
        }
        reason = "conflicting_copies" if len(signatures) > 1 else "eligible"
        try:
            price = Fraction(copies[0]["price_native"])
            if price < 0 or (key[3] == "base" and price == 0):
                reason = "invalid_price"
        except (ValueError, ZeroDivisionError):
            reason = "invalid_price"
        if reason == "eligible":
            quotes[key] = copies[0]
        key_rows.append(
            dict(
                marketing_year=key[0],
                date=key[1],
                market=key[2],
                grade=key[3],
                copies=len(copies),
                source_rows=",".join(r["source_row"] for r in copies),
                status=reason,
            )
        )
    pairs = []
    ledger = []
    coverage = []
    market_bindings = json.loads(
        (ROOT / "data/market_bindings.json").read_text(encoding="utf-8")
    )
    for year in sorted(dates):
        for market in market_bindings[year]:
            counts = Counter()
            for date in sorted(dates[year]):
                base = quotes.get((year, date, market, "base"))
                added = quotes.get((year, date, market, "added"))
                reason = (
                    "eligible"
                    if base and added
                    else ("base_unavailable" if not base else "added_unavailable")
                )
                counts[reason] += 1
                ledger.append(
                    dict(marketing_year=year, date=date, market=market, status=reason)
                )
                if reason == "eligible":
                    pairs.append(
                        dict(
                            marketing_year=year,
                            date=date,
                            market=market,
                            base_native=base["price_native"],
                            added_native=added["price_native"],
                            base_row=base["source_row"],
                            added_row=added["source_row"],
                            unit=base["unit"],
                            other_quality_convention=base["other_quality_convention"],
                        )
                    )
            coverage.append(
                dict(
                    marketing_year=year,
                    market=market,
                    source_dates=len(dates[year]),
                    paired_days=counts["eligible"],
                    base_unavailable=counts["base_unavailable"],
                    added_unavailable=counts["added_unavailable"],
                    minimum_required=100,
                    gate="pass" if counts["eligible"] >= 100 else "fail",
                )
            )
    return key_rows, pairs, ledger, coverage, reasons


def main():
    with gzip.open(
        ROOT / "data/quote_rows.csv.gz", "rt", encoding="utf-8", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream))
    keys, pairs, ledger, coverage, reasons = qualify(rows)
    for name, items in [
        ("quote_key_ledger.csv", keys),
        ("pairs.csv", pairs),
        ("pair_ledger.csv", ledger),
        ("coverage.csv", coverage),
    ]:
        assert items, "No source-qualified records; preserve source and stop"
        write_csv(ROOT / "data" / name, items)
    summary = dict(
        raw_projected_rows=len(rows),
        key_groups=len(keys),
        identical_extra_copies=sum(
            int(r["copies"]) - 1 for r in keys if r["status"] == "eligible"
        ),
        conflicting_keys=sum(r["status"] == "conflicting_copies" for r in keys),
        paired_quote_days=len(pairs),
        coverage_gate=(
            "pass"
            if len(coverage) == 21 and all(r["gate"] == "pass" for r in coverage)
            else "fail"
        ),
        source_reasons=dict(reasons),
        sha256={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "data").glob("*.csv"))
        },
    )
    (ROOT / "data/input_receipt.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    assert (
        summary["coverage_gate"] == "pass"
    ), "Fixed source coverage gate failed; do not score"


if __name__ == "__main__":
    main()
