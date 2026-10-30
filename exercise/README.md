# Implementation exercise: stop a composition-only price alert

A feed first lists one cotton quality at 80 cents per pound. Its next snapshot keeps that quote at 80 and adds another quality at 88. These prices and snapshots are **authored examples**, not USDA quotations or customer incidents.

The mean rises from 80 to 84, so a grade-blind comparison emits a 5 percent change. The original quality changed by zero. Implement a comparison that makes the intended price series explicit.

1. Read `examples/old-authored.json` and `examples/new-authored.json` without changing them.
2. Require market, source date, units, other-quality convention and color/leaf/staple identity. Use the native decimal price token rather than binary rounding at a threshold.
3. Compare the identical base definition. Return an unavailable status when its identity is absent, its copies conflict or its price is invalid. An unavailable result is not a negative prediction.
4. Test the unchanged base, a real authored signed change, the exact 2 percent threshold, a changed staple, missing base, mismatched units and conflicting copies.
5. Explain why this deterministic safeguard does not estimate live anomaly precision, prove business savings or forecast cotton prices.

The reference implementation is [src/alerts.py](../src/alerts.py), with executable cases in [tests/test_alerts.py](../tests/test_alerts.py). Try the exercise before reading it. The CLI can compare your result:

```powershell
python src/cli.py examples/old-authored.json examples/new-authored.json
python src/cli.py examples/old-authored.json examples/new-authored.json --rule grade_blind
```

The expected changes are exactly `0` and `1/20`. A production integration would still need a documented report-version crosswalk, source-arrival monitoring, live failure labels and shadow evaluation. This repository supplies a bounded local exercise and historical controlled replay.
