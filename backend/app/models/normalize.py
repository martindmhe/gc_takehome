def normalize_region(value: str) -> str:
    """Canonical region form: trimmed, single-spaced, lowercase ("  New  York " -> "new york").

    Leads and routing rules both store this form, so routing is an exact match.
    """
    return " ".join(value.split()).lower()


def region_label(value: str) -> str:
    """Display label for a stored region: "new york" -> "New York"."""
    return value.title()
