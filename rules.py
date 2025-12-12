# rules.py
"""
Centralized rule definitions and helper utilities for scoring and explanations.
"""

from typing import Dict, List

# Canonical default weights (tune these to change behavior)
DEFAULT_WEIGHTS: Dict[str, int] = {
    "same_category_same_brand": 4,
    "same_category": 2,
    "similar_category": 1,
    "same_brand": 1,
    "attribute_match": 1,     # per attribute matched
    "cheaper_bonus": 1,
    "in_stock_bonus": 2
}

# Human-readable descriptions for each rule — used when building explanations
RULES_INFO: Dict[str, str] = {
    "same_category_same_brand": "Same category and same brand",
    "same_category": "Same category",
    "similar_category": "Category is similar (fallback)",
    "same_brand": "Same brand",
    "attribute_match": "Shares important attributes",
    "cheaper_or_equal": "Cheaper or equal price than original",
    "in_stock": "Available (in stock)",
}

# Rule priority/order for explanation formatting (optional)
RULE_PRIORITY: List[str] = [
    "same_category_same_brand",
    "same_category",
    "same_brand",
    "similar_category",
    "attribute_match",
    "cheaper_or_equal",
    "in_stock",
]


def format_explanation(fired_rules: List[str]) -> List[str]:
    """
    Convert fired rule keys (and attribute_match(n) style strings) into nice explanation lines.
    Keeps ordering defined in RULE_PRIORITY for readability.
    """
    lines: List[str] = []
    # attribute matches (like "attribute_match(2)")
    attr_matches = [r for r in fired_rules if r.startswith("attribute_match")]
    other = [r for r in fired_rules if not r.startswith("attribute_match")]

    # Sort other by priority
    def _prio_key(r):
        try:
            return RULE_PRIORITY.index(r)
        except ValueError:
            return len(RULE_PRIORITY)

    other_sorted = sorted(other, key=_prio_key)

    for r in other_sorted:
        if r in RULES_INFO:
            lines.append(RULES_INFO[r])
        else:
            # fallback: if it's e.g. "attribute_match(2)" handle later; otherwise raw
            lines.append(r)

    # Append attribute match messages at the end (more specific)
    for a in attr_matches:
        import re
        m = re.search(r"\((\d+)\)", a)
        if m:
            lines.append(f"Shares {m.group(1)} attribute(s)")
        else:
            lines.append("Shares attributes")

    return lines
