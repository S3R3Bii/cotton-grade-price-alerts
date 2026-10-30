"""Check source values, actual SVG coordinates and every exported figure hash."""

import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SVG = "{http://www.w3.org/2000/svg}"


def read(path):
    return list(csv.DictReader((ROOT / path).open(encoding="utf-8", newline="")))


def points(node):
    path = node.find(".//" + SVG + "path")
    assert path is not None
    values = [
        float(v)
        for v in re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", path.attrib["d"])
    ]
    assert len(values) % 2 == 0
    return list(zip(values[::2], values[1::2]))


def main():
    premiums = read("results/held/source_premiums.csv")
    summary = read("results/held/summary.csv")
    metadata = json.loads((ROOT / "figures/value_map.json").read_text(encoding="utf-8"))
    coordinate_checks = value_checks = hash_checks = 0
    markets = list(
        json.loads((ROOT / "data/market_bindings.json").read_text())["2024-2025"]
    )
    for fig in metadata:
        tree = ET.parse(ROOT / "figures" / (fig["figure"] + ".svg"))
        ids = {n.get("id"): n for n in tree.iter() if n.get("id")}
        areas = []
        for ai, limits in enumerate(fig["axes"]):
            pts = points(ids["data-area-" + str(ai)])
            areas.append(
                (
                    min(x for x, y in pts),
                    max(x for x, y in pts),
                    min(y for x, y in pts),
                    max(y for x, y in pts),
                )
            )
        for item in fig["items"]:
            query = item["query"]
            kind = query["kind"]
            ai = 0
            actual = points(ids[item["id"]])
            if kind.startswith("composition"):
                index = markets.index(query["market"])
                values = sorted(
                    Fraction(r["composition_only_mean_change"]) * 100
                    for r in premiums
                    if r["market"] == query["market"]
                )
                median = values[len(values) // 2]
                lo, hi = values[0], values[-1]
                maxvalue = (
                    max(
                        float(Fraction(r["composition_only_mean_change"]) * 100)
                        for r in premiums
                    )
                    + 1.35
                )
                assert fig["axes"][0] == dict(xlim=[0, maxvalue], ylim=[6.7, -0.7])
                expected_value = median if kind == "composition_median" else lo
                expected_points = (
                    [
                        (0, index - 0.23),
                        (float(median), index - 0.23),
                        (float(median), index + 0.23),
                        (0, index + 0.23),
                    ]
                    if kind == "composition_median"
                    else [(float(lo), index), (float(hi), index)]
                )
                value_checks += 1 if kind == "composition_median" else 2
            elif kind == "error_rate":
                index = ["1/100", "1/50", "1/20"].index(query["threshold"])
                row = next(
                    r
                    for r in summary
                    if r["rule"] == "grade_blind"
                    and r["threshold"] == query["threshold"]
                    and r["expansion"] == "1"
                    and r["identity_mode"] == "normal"
                )
                num = query["numerator"]
                den = (
                    int(row["fp"]) + int(row["tn"])
                    if num == "fp"
                    else int(row["fn"]) + int(row["tp"])
                )
                expected_value = Fraction(int(row[num]), den) * 100
                ai = 0 if num == "fp" else 1
                assert fig["axes"][ai] == dict(xlim=[-0.6, 2.6], ylim=[0, 116])
                expected_points = [
                    (index - 0.29, 0),
                    (index + 0.29, 0),
                    (index + 0.29, float(expected_value)),
                    (index - 0.29, float(expected_value)),
                ]
                value_checks += 1
            else:
                assert kind == "coverage"
                index = ["normal", "missing_base", "changed_quality"].index(
                    query["identity_mode"]
                )
                rule = query["rule"]
                selected = [
                    r
                    for r in summary
                    if r["rule"] == rule
                    and r["identity_mode"] == query["identity_mode"]
                ]
                total = sum(int(r["cases"]) for r in selected)
                emitted = total - sum(int(r["abstain"]) for r in selected)
                expected_value = Fraction(emitted, total) * 100
                center = index + (-0.18 if rule == "grade_blind" else 0.18)
                assert fig["axes"][0] == dict(xlim=[-0.6, 2.6], ylim=[0, 132])
                expected_points = [
                    (center - 0.16, 0),
                    (center + 0.16, 0),
                    (center + 0.16, float(expected_value)),
                    (center - 0.16, float(expected_value)),
                ]
                value_checks += 1
            assert Fraction(item["value_exact"]) == expected_value
            left, right, top, bottom = areas[ai]
            limits = fig["axes"][ai]
            xmin, xmax = limits["xlim"]
            ymin, ymax = limits["ylim"]
            converted = [
                (
                    left + (x - xmin) / (xmax - xmin) * (right - left),
                    bottom - (y - ymin) / (ymax - ymin) * (bottom - top),
                )
                for x, y in expected_points
            ]
            assert len(actual) == len(converted), (item["id"], actual, converted)
            for a, b in zip(actual, converted):
                assert max(abs(x - y) for x, y in zip(a, b)) < 0.00002, (
                    item["id"],
                    a,
                    b,
                )
                coordinate_checks += 2
            mapped = item["vertices_svg"]
            mapped = (
                mapped[:-1] if len(mapped) > 2 and mapped[0] == mapped[-1] else mapped
            )
            for a, b in zip(actual, mapped, strict=True):
                assert max(abs(x - y) for x, y in zip(a, b)) < 0.00002
        for path, digest in fig["files"].items():
            assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
            hash_checks += 1
    result = dict(
        status="pass",
        figures=3,
        value_checks=value_checks,
        actual_svg_coordinate_checks=coordinate_checks,
        export_hash_checks=hash_checks,
        limits="Finite source-value/geometry/hash checks; rendered figures also require visual inspection",
    )
    (ROOT / "figures/verification.json").write_bytes(
        (json.dumps(result, indent=2) + "\n").encode()
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
