"""Exact price comparisons with an explicit same-quality key and abstention."""

from fractions import Fraction


def compare(old, new, rule):
    """Return a fractional change or an unavailable-identity reason."""
    if rule not in {"grade_blind", "quality_matched"}:
        raise ValueError("Unknown comparison rule")
    try:
        base = Fraction(old["price"])
    except (ValueError, TypeError, ZeroDivisionError):
        return None, "invalid_baseline"
    if base <= 0:
        return None, "invalid_baseline"
    common = ("market", "date", "unit", "other_quality_convention")
    if old.get("unit") != "cents_per_pound":
        return None, "unit_unavailable"
    if any(any(row.get(k) != old.get(k) for k in common) for row in new):
        return None, "common_identity_mismatch"
    candidates = (
        new
        if rule == "grade_blind"
        else [r for r in new if r.get("quality") == old.get("quality")]
    )
    if not candidates:
        return None, (
            "quality_unavailable" if rule == "quality_matched" else "empty_snapshot"
        )
    try:
        values = [Fraction(r["price"]) for r in candidates]
    except (ValueError, TypeError, ZeroDivisionError):
        return None, "invalid_price"
    if any(v < 0 for v in values):
        return None, "invalid_price"
    if rule == "quality_matched":
        if len(set(values)) > 1:
            return None, "conflicting_quality_copies"
        value = values[0]
    else:
        value = sum(values, Fraction()) / len(values)
    return value / base - 1, "available"


def alert(change, threshold):
    limit = Fraction(threshold)
    if limit <= 0:
        raise ValueError("Threshold must be positive")
    return None if change is None else abs(change) >= limit


def snapshot(pair, expansion, shock, identity_mode):
    """Create separately labeled authored values, leaving source tokens untouched."""
    if identity_mode not in {"normal", "missing_base", "changed_quality"}:
        raise ValueError("Unknown authored case")
    old = {k: pair[k] for k in ["market", "date", "unit", "other_quality_convention"]}
    old.update(quality="41/4/34", price=pair["base_native"])
    new = []
    if identity_mode != "missing_base":
        base = old.copy()
        base["price"] = str(Fraction(pair["base_native"]) * (1 + Fraction(shock)))
        if identity_mode == "changed_quality":
            base["quality"] = "41/4/35_AUTHORED"
        new.append(base)
    if expansion:
        added = old.copy()
        added.update(
            quality="31/3/36",
            price=str(Fraction(pair["added_native"]) * (1 + Fraction(shock))),
        )
        new.append(added)
    return old, new
