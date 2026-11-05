def normalize_region(value: str) -> str:
    """Canonical region form: trimmed, single-spaced, lowercase ("  New  York " -> "new york").

    Leads and routing rules both store this form, so routing is an exact match.
    """
    return " ".join(value.split()).lower()
