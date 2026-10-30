"""Independently read original selected cells with Openpyxl and stdlib OOXML."""

import argparse
import csv
import gzip
import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
TAG = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-dir", type=Path, required=True)
    args = parser.parse_args()
    with gzip.open(
        ROOT / "data/quote_rows.csv.gz", "rt", encoding="utf-8", newline=""
    ) as stream:
        projection = list(csv.DictReader(stream))
    source_receipt = json.loads(
        (ROOT / "data/source_receipt.json").read_text(encoding="utf-8")
    )
    checks = 0
    reports = []
    for source in source_receipt["source_workbooks"]:
        path = args.private_dir / source["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
        checks += 1
        selected = {
            int(r["source_row"]): r
            for r in projection
            if r["workbook"] == source["file"]
        }
        assert len(selected) == sum(r["workbook"] == source["file"] for r in projection)
        book = openpyxl.load_workbook(path, read_only=True, data_only=False)
        sheet = book["C-L-S"]
        observed = {}
        grid_count = 0
        for row_index, row in enumerate(sheet.iter_rows(min_col=1, max_col=9), 1):
            if row_index == 1:
                assert [c.value for c in row] == [
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
                checks += 9
                continue
            grid_count += 1
            target = tuple(str(c.value) for c in row[4:7])
            if target not in {("41", "4", "34"), ("31", "3", "36")}:
                continue
            assert row_index in selected
            record = selected[row_index]
            observed[row_index] = record
            for col, field in [
                (0, "source_name"),
                (2, "type"),
                (3, "market"),
                (4, "color"),
                (5, "leaf"),
                (6, "staple"),
            ]:
                assert str(row[col].value) == record[field], (
                    source["file"],
                    row_index,
                    field,
                )
                checks += 1
            assert (
                isinstance(row[1].value, datetime)
                and row[1].value.date().isoformat() == record["date"]
            )
            checks += 1
            expected_types = json.loads(record["native_types"])
            for col, letter in enumerate("ABCDEFGHI"):
                expected = expected_types[letter]
                actual = row[col].data_type
                assert actual == (
                    "d" if letter == "B" and expected == "n" else expected
                ), (source["file"], row_index, letter, actual, expected)
                assert actual != "f" and not record["formula_cells"]
                checks += 2
            for col, field in [(7, "difference_native"), (8, "price_native")]:
                assert float(Decimal(record[field])) == row[col].value, (
                    source["file"],
                    row_index,
                    field,
                )
                checks += 1
        assert observed == selected and grid_count == source["counts"]["all_grid_rows"]
        checks += 2
        book.close()
        with ZipFile(path) as z:
            wb = ET.fromstring(z.read("xl/workbook.xml"))
            relmap = {
                r.attrib["Id"]: r.attrib["Target"]
                for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            }
            sheet = next(
                s for s in wb.find(TAG + "sheets") if s.attrib["name"] == "C-L-S"
            )
            target = relmap[
                sheet.attrib[
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                ]
            ]
            target = target.lstrip("/") if target.startswith("/") else "xl/" + target
            raw_seen = set()
            with z.open(target) as stream:
                context = ET.iterparse(stream, events=("start", "end"))
                _, root = next(context)
                for event, node in context:
                    if event != "end" or node.tag != TAG + "row":
                        continue
                    index = int(node.attrib["r"])
                    if index in selected:
                        wanted = selected[index]
                        bycol = {
                            "".join(c for c in cell.attrib["r"] if c.isalpha()): cell
                            for cell in node
                        }
                        for letter, field in [
                            ("B", "date_serial"),
                            ("H", "difference_native"),
                            ("I", "price_native"),
                        ]:
                            assert bycol[letter].findtext(TAG + "v") == wanted[field], (
                                source["file"],
                                index,
                                field,
                            )
                            checks += 1
                        raw_seen.add(index)
                    node.clear()
                    root.clear()
            assert raw_seen == set(selected)
            checks += 1
        reports.append(
            dict(
                file=source["file"],
                selected_rows=len(selected),
                all_grid_rows=grid_count,
                sha256=source["sha256"],
            )
        )
        print(
            "SOURCE_RECONCILED", source["file"], len(selected), grid_count, flush=True
        )
    report = dict(
        status="pass",
        checks=checks,
        readers=[
            "Openpyxl read_only original rows",
            "independent stdlib OOXML native selected numeric tokens",
        ],
        sources=reports,
        source_projection_sha256=hashlib.sha256(
            (ROOT / "data/quote_rows.csv.gz").read_bytes()
        ).hexdigest(),
        limitations=[
            "These are quotation-grid facts, not transactions or independent market anomalies.",
            "All original source bytes retained; no workbook edit, recalculation or export.",
        ],
    )
    (ROOT / "data/source_verification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "pass", "checks": checks}), flush=True)


if __name__ == "__main__":
    main()
