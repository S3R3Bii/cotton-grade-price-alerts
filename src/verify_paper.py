"""Bind displayed paper quantities to exports and inspect the actual PDF text."""

import csv
import hashlib
import json
import unicodedata
from fractions import Fraction
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return list(csv.DictReader((ROOT / path).open(encoding="utf-8", newline="")))


def main():
    reader = PdfReader(ROOT / "paper/manuscript.pdf")
    assert len(reader.pages) == 6
    pages = [unicodedata.normalize("NFKC", p.extract_text()) for p in reader.pages]
    assert all(len(p) > 600 for p in pages)
    ledger = json.loads(
        (ROOT / "paper/display_ledger.json").read_text(encoding="utf-8")
    )
    checks = 1
    for record in ledger:
        query = record["query"]
        kind = query["kind"]
        if kind == "metric":
            row = next(
                r
                for r in read("results/" + query["stage"] + "/summary.csv")
                if r["rule"] == query["rule"]
                and r["threshold"] == query["threshold"]
                and r["expansion"] == "1"
                and r["identity_mode"] == "normal"
            )
            value = Fraction(row[query["field"]])
            value = value if record["format"] == ",d" else value * 100
        elif kind == "json":
            value = json.loads((ROOT / query["path"]).read_text(encoding="utf-8"))[
                query["field"]
            ]
        else:
            coverage = [
                r
                for r in read("data/coverage.csv")
                if r["marketing_year"] == query["year"]
            ]
            if kind == "coverage_days":
                values = {r["paired_days"] for r in coverage}
                assert len(values) == 1
                value = int(values.pop())
            else:
                assert kind == "coverage_total"
                value = sum(int(r["paired_days"]) for r in coverage)
        expected = (
            format(int(value), ",d")
            if record["format"] == ",d"
            else format(float(value), record["format"])
        )
        assert expected == record["text"] and expected in pages[record["page"]], record
        checks += 2
    text = " ".join(pages).replace("\n", " ")
    for phrase in [
        "not evidence of live anomaly-detection precision",
        "not observed temporal price jumps",
        "no analyst-blindness",
        "37 files",
        "28 finite fixtures",
        "not a prospective",
        "Abstentions",
        "not natural market-anomaly prevalence",
        "No financial saving",
        "runtime",
        "third-party",
    ]:
        assert phrase.lower() in text.lower(), phrase
        checks += 1
    for name in ["composition_effects", "alert_errors", "identity_coverage"]:
        assert (ROOT / "paper/images" / (name + ".pdf")).read_bytes() == (
            ROOT / "figures" / (name + ".pdf")
        ).read_bytes()
        checks += 1
    result = dict(
        status="pass",
        pages=6,
        source_bound_displays=len(ledger),
        checks=checks,
        pdf_sha256=hashlib.sha256(
            (ROOT / "paper/manuscript.pdf").read_bytes()
        ).hexdigest(),
        scope="Finite source arithmetic, actual extracted PDF quantities, required qualifications and figure-byte identity; all rendered pages require separate visual inspection",
    )
    (ROOT / "paper/verification.json").write_bytes(
        (json.dumps(result, indent=2) + "\n").encode()
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
