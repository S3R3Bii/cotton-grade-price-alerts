"""Compare two explicitly identified quote snapshots from local JSON files."""

import argparse
import json
from fractions import Fraction
from pathlib import Path

from alerts import alert, compare


def main():
    parser = argparse.ArgumentParser(
        description="Preserve cotton quote identity before emitting a price alert."
    )
    parser.add_argument(
        "old_snapshot",
        type=Path,
        help="One old quote object; native price token and full identity required",
    )
    parser.add_argument(
        "new_snapshot", type=Path, help="JSON array of new quote objects"
    )
    parser.add_argument(
        "--rule", choices=["quality_matched", "grade_blind"], default="quality_matched"
    )
    parser.add_argument(
        "--threshold",
        default="1/50",
        help="Positive fractional change; 1/50 means 2 percent",
    )
    args = parser.parse_args()
    try:
        old = json.loads(args.old_snapshot.read_text(encoding="utf-8"))
        new = json.loads(args.new_snapshot.read_text(encoding="utf-8"))
        if (
            not isinstance(old, dict)
            or not isinstance(new, list)
            or any(not isinstance(r, dict) for r in new)
        ):
            raise ValueError(
                "Expected one old quote object and an array of new quote objects"
            )
        threshold = Fraction(args.threshold)
        estimate, reason = compare(old, new, args.rule)
        decision = alert(estimate, threshold)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            dict(
                rule=args.rule,
                threshold_fraction=str(threshold),
                estimated_change_fraction=None if estimate is None else str(estimate),
                alert=decision,
                status=reason,
                scope="Local quotation identity comparison; no trading recommendation or anomaly probability",
            )
        )
    )


if __name__ == "__main__":
    main()
