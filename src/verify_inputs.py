"""Recompute source-key eligibility and paired coverage with SQLite and Decimal."""

import csv
import gzip
import hashlib
import json
import sqlite3
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    with gzip.open(
        ROOT / "data/quote_rows.csv.gz", "rt", encoding="utf-8", newline=""
    ) as f:
        raw = list(csv.DictReader(f))
    connection = sqlite3.connect(":memory:")
    fields = list(raw[0])
    connection.execute(
        "CREATE TABLE quotes (" + ",".join('"' + k + '" TEXT' for k in fields) + ")"
    )
    connection.executemany(
        "INSERT INTO quotes VALUES (" + ",".join("?" for _ in fields) + ")",
        [[r[k] for k in fields] for r in raw],
    )
    connection.row_factory = sqlite3.Row
    bindings = json.loads(
        (ROOT / "data/market_bindings.json").read_text(encoding="utf-8")
    )
    checks = 0
    valid = {}
    expected_keys = {}
    keys = connection.execute(
        "SELECT marketing_year,date,market,grade,COUNT(*) AS copies,GROUP_CONCAT(source_row,',') AS source_rows FROM quotes WHERE reason='source_eligible' GROUP BY marketing_year,date,market,grade ORDER BY marketing_year,date,market,grade"
    ).fetchall()
    for row in keys:
        copies = connection.execute(
            "SELECT * FROM quotes WHERE marketing_year=? AND date=? AND market=? AND grade=? AND reason=?",
            (*tuple(row)[:4], "source_eligible"),
        ).fetchall()
        signatures = {
            tuple(
                r[k]
                for k in [
                    "price_native",
                    "difference_native",
                    "type",
                    "color",
                    "leaf",
                    "staple",
                    "unit",
                    "other_quality_convention",
                ]
            )
            for r in copies
        }
        status = "eligible"
        if len(signatures) != 1:
            status = "conflicting_copies"
        try:
            value = Decimal(copies[0]["price_native"])
            if (
                not value.is_finite()
                or value < 0
                or (row["grade"] == "base" and value == 0)
            ):
                status = "invalid_price"
        except InvalidOperation:
            status = "invalid_price"
        key = tuple(row)[:4]
        expected_keys[key] = dict(row) | {"status": status}
        if status == "eligible":
            valid[key] = dict(copies[0])
    actual_keys = list(
        csv.DictReader(
            (ROOT / "data/quote_key_ledger.csv").open(encoding="utf-8", newline="")
        )
    )
    assert len(actual_keys) == len(expected_keys)
    checks += 1
    for row in actual_keys:
        key = tuple(row[k] for k in ["marketing_year", "date", "market", "grade"])
        expected = expected_keys[key]
        for field in ["copies", "source_rows", "status"]:
            assert row[field] == str(expected[field]), (key, field)
            checks += 1
    actual_pairs = list(
        csv.DictReader((ROOT / "data/pairs.csv").open(encoding="utf-8", newline=""))
    )
    actual_pair_map = {
        (r["marketing_year"], r["date"], r["market"]): r for r in actual_pairs
    }
    assert len(actual_pair_map) == len(actual_pairs)
    checks += 1
    actual_ledger = list(
        csv.DictReader(
            (ROOT / "data/pair_ledger.csv").open(encoding="utf-8", newline="")
        )
    )
    ledger = {
        (r["marketing_year"], r["date"], r["market"]): r["status"]
        for r in actual_ledger
    }
    coverage = list(
        csv.DictReader((ROOT / "data/coverage.csv").open(encoding="utf-8", newline=""))
    )
    coverage_map = {(r["marketing_year"], r["market"]): r for r in coverage}
    expected_count = 0
    expected_ledger = {}
    expected_pair_count = 0
    for year, markets in bindings.items():
        dates = [
            r[0]
            for r in connection.execute(
                "SELECT DISTINCT date FROM quotes WHERE marketing_year=? AND reason='source_eligible' ORDER BY date",
                (year,),
            )
        ]
        for market in markets:
            count = 0
            missing_base = 0
            missing_added = 0
            for day in dates:
                base = valid.get((year, day, market, "base"))
                added = valid.get((year, day, market, "added"))
                key = (year, day, market)
                expected_ledger[key] = (
                    "eligible"
                    if base and added
                    else "base_unavailable" if not base else "added_unavailable"
                )
                if not base:
                    missing_base += 1
                elif not added:
                    missing_added += 1
                else:
                    count += 1
                    row = actual_pair_map[key]
                    for field, value in [
                        ("base_native", base["price_native"]),
                        ("added_native", added["price_native"]),
                        ("base_row", base["source_row"]),
                        ("added_row", added["source_row"]),
                        ("unit", base["unit"]),
                        ("other_quality_convention", base["other_quality_convention"]),
                    ]:
                        assert row[field] == value, (key, field)
                        checks += 1
                    expected_pair_count += 1
            row = coverage_map[year, market]
            for field, value in [
                ("source_dates", len(dates)),
                ("paired_days", count),
                ("base_unavailable", missing_base),
                ("added_unavailable", missing_added),
                ("minimum_required", 100),
                ("gate", "pass" if count >= 100 else "fail"),
            ]:
                assert row[field] == str(value)
                checks += 1
            assert count >= 100
            checks += 1
            expected_count += 1
    assert (
        ledger == expected_ledger
        and len(coverage) == expected_count == 21
        and len(actual_pairs) == expected_pair_count
    )
    checks += 3
    report = dict(
        status="pass",
        checks=checks,
        independent_method="SQLite full-key grouping and Decimal sign/finite checks; independent coverage enumeration",
        paired_days=expected_pair_count,
        market_year_groups=21,
        gate="At least 100 paired quote-days in every exact native market/year",
        sha256={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "data").glob("*.csv"))
        },
    )
    (ROOT / "data/input_verification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
