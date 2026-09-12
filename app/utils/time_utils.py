from __future__ import annotations

from datetime import datetime


def normalize_time(value: str) -> str | None:
    """Normalize a structured clock value to canonical HH:MM.

    Natural-language time interpretation belongs to Mistral tool routing. This
    helper only validates common clock representations returned or supplied as
    structured values.
    """
    text = str(value).strip().strip("\"\'").rstrip(".,;").strip()
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.strptime(text.upper(), fmt).strftime("%H:%M")
        except ValueError:
            continue
    return None
