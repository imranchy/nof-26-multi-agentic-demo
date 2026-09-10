from __future__ import annotations

from datetime import datetime

import dateparser


def normalize_time(value: str) -> str | None:
    """Normalize an explicit operator clock expression to canonical HH:MM."""
    parsed = dateparser.parse(
        value,
        settings={
            # We only care about the clock component. A fixed base keeps
            # time-only parsing deterministic and independent of today's date.
            "RELATIVE_BASE": datetime(2000, 1, 1),
        },
    )

    if parsed is None:
        return None

    return parsed.strftime("%H:%M")
