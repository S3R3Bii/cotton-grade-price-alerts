"""Project exact native spot-quote tokens; retain originals outside the repository."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
MARKETS = (
    "Southeast",
    "North Delta",
    "South Delta",
    "East TX-OK",
    "West Texas",
    "Desert SW",
    "SJ Valley",
)
GRADES = {("41", "4", "34"): "base", ("31", "3", "36"): "added"}
HEADERS = [
    "Source.Name",
    "Date",
    "Type",
    "Market",
    "Color",
    "Leaf",
    "Staple",
    "Difference",
    "Physical Price",
]
FIELDS = [
    "marketing_year",
    "workbook",
    "sheet",
    "source_row",
    "source_name",
    "date_serial",
    "date",
    "type",
    "market",
    "color",
    "leaf",
    "staple",
    "difference_native",
    "price_native",
    "grade",
    "unit",
    "other_quality_convention",
    "native_types",
    "formula_cells",
    "cache_states",
    "reason",
]


def contents(z):
    strings = []
    if "xl/sharedStrings.xml" in z.namelist():
        tree = etree.fromstring(z.read("xl/sharedStrings.xml"))
        strings = ["".join(item.itertext()) for item in tree]
    rels = etree.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    paths = {r.get("Id"): r.get("Target") for r in rels}
    book = etree.fromstring(z.read("xl/workbook.xml"))
    props = book.find(NS + "workbookPr")
    assert props is None or props.get("date1904", "0") in {
        "0",
        "false",
    }, "Unexpected workbook date epoch"
    sheets = {}
    for sheet in book.find(NS + "sheets"):
        path = paths[
            sheet.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
        ]
        sheets[sheet.get("name")] = (
            path.lstrip("/") if path.startswith("/") else "xl/" + path
        )
    return strings, sheets


def rows(z, path, strings):
    with z.open(path) as stream:
        for _, row in etree.iterparse(stream, events=("end",), tag=NS + "row"):
            cells = {}
            for cell in row:
                if cell.tag != NS + "c":
                    continue
                ref = cell.get("r")
                kind = cell.get("t", "n")
                v = cell.find(NS + "v")
                f = cell.find(NS + "f")
                token = "" if v is None or v.text is None else v.text
                if kind == "s":
                    token = strings[int(token)] if token else ""
                elif kind == "inlineStr":
                    token = "".join(cell.find(NS + "is").itertext())
                cells["".join(c for c in ref if c.isalpha())] = {
                    "ref": ref,
                    "value": token,
                    "type": kind,
                    "formula": f is not None,
                    "cache": "absent" if v is None else "present",
                }
            yield int(row.get("r")), cells
            row.clear()
            while row.getprevious() is not None:
                del row.getparent()[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-dir", type=Path, required=True)
    args = parser.parse_args()
    receipts = json.loads(
        (args.private_dir / "requests.json").read_text(encoding="utf-8")
    )
    selected = []
    source_receipts = []
    market_bindings = json.loads(
        (ROOT / "data/market_bindings.json").read_text(encoding="utf-8")
    )
    for item in receipts:
        market_map = market_bindings[item["marketing_year"]]
        source = args.private_dir / item["file"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == item["sha256"]
        counts = Counter()
        base_lookup = {}
        base_conflicts = set()
        base_checks = 0
        with ZipFile(source) as z:
            strings, sheets = contents(z)
            for index, cells in rows(z, sheets["Basis and Bales"], strings):
                vals = [cells.get(c, {}).get("value", "") for c in "ABCDEFGHI"]
                if index == 1:
                    assert vals[:7] == [
                        "Source.Name",
                        "Date",
                        "Type",
                        "Market",
                        "Basis",
                        "Basis Month",
                        "41-4-34",
                    ]
                    continue
                if vals[2] == "Upland" and vals[3] in set(market_map.values()):
                    key = (vals[1], vals[3])
                    value = vals[6]
                    if key in base_lookup and base_lookup[key] != value:
                        base_conflicts.add(key)
                    base_lookup[key] = value
            for index, cells in rows(z, sheets["C-L-S"], strings):
                vals = [cells.get(c, {}).get("value", "") for c in "ABCDEFGHI"]
                if index == 1:
                    assert vals == HEADERS, (source.name, vals)
                    continue
                counts["all_grid_rows"] += 1
                if tuple(vals[4:7]) not in GRADES:
                    continue
                counts["exact_grade_matches"] += 1
                reason = []
                if vals[2] != "Upland":
                    reason.append("not_upland")
                if vals[3] not in market_map:
                    reason.append("unexpected_market")
                formulas = [v["ref"] for v in cells.values() if v["formula"]]
                if formulas:
                    reason.append("formula_unverified")
                try:
                    serial = int(vals[1])
                    assert str(serial) == vals[1] and serial >= 61
                    date = (
                        (datetime(1899, 12, 30) + timedelta(days=serial))
                        .date()
                        .isoformat()
                    )
                except (ValueError, AssertionError):
                    date = ""
                    reason.append("invalid_date")
                if cells.get("I", {}).get("type") != "n" or not vals[8]:
                    reason.append("non_numeric_or_missing_price")
                if GRADES[tuple(vals[4:7])] == "base" and not reason:
                    from decimal import Decimal

                    key = (vals[1], market_map[vals[3]])
                    assert key in base_lookup and key not in base_conflicts, (
                        "unavailable_headline_base",
                        key,
                    )
                    assert Decimal(vals[8]) == Decimal(base_lookup[key]), (
                        "grid_headline_disagreement",
                        key,
                    )
                    base_checks += 1
                r = dict(
                    zip(
                        FIELDS,
                        [
                            item["marketing_year"],
                            item["file"],
                            "C-L-S",
                            str(index),
                            vals[0],
                            vals[1],
                            date,
                            vals[2],
                            vals[3],
                            *vals[4:7],
                            vals[7],
                            vals[8],
                            GRADES[tuple(vals[4:7])],
                            "cents_per_pound",
                            "USDA_CLS_base_other_factors",
                            json.dumps(
                                {
                                    c: cells.get(c, {}).get("type", "absent")
                                    for c in "ABCDEFGHI"
                                },
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            ",".join(formulas),
                            json.dumps(
                                {
                                    c: cells.get(c, {}).get("cache", "absent")
                                    for c in "ABCDEFGHI"
                                },
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            ";".join(reason) or "source_eligible",
                        ],
                    )
                )
                selected.append(r)
                counts[r["reason"]] += 1
        source_receipts.append(
            {
                k: item[k]
                for k in [
                    "marketing_year",
                    "file",
                    "url",
                    "status",
                    "bytes",
                    "sha256",
                    "started_utc",
                    "completed_utc",
                    "protocol_commit",
                    "python",
                ]
            }
            | {
                "sheets": list(sheets),
                "counts": dict(counts),
                "grid_headline_base_checks": base_checks,
            }
        )
        print(
            json.dumps(
                {
                    "year": item["marketing_year"],
                    "counts": dict(counts),
                    "base_checks": base_checks,
                }
            ),
            flush=True,
        )
    output = ROOT / "data/quote_rows.csv.gz"
    assert not output.exists()
    with output.open("wb") as raw, gzip.GzipFile(
        filename="", fileobj=raw, mode="wb", mtime=0
    ) as compressed, io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
        writer = csv.DictWriter(text, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(selected)
    (ROOT / "data/source_receipt.json").write_text(
        json.dumps(
            {
                "source_workbooks": source_receipts,
                "projection_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "rows": len(selected),
                "price_semantics": "Native Physical Price cents/lb; no rounding or reconstruction",
                "rights_scope": "Minimal attributed USDA spot facts; original workbook and ICE data excluded",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("PROJECTION_WRITTEN", len(selected), flush=True)


if __name__ == "__main__":
    main()
