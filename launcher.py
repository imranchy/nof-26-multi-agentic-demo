from __future__ import annotations

import sys
from pathlib import Path

from streamlit.web import cli as stcli

if __name__ == "__main__":
    ui = Path(__file__).resolve().parent / "app" / "ui.py"
    sys.argv = ["streamlit", "run", str(ui), "--server.headless=true", "--browser.gatherUsageStats=false"]
    raise SystemExit(stcli.main())

