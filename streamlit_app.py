"""Cloud entrypoint (Streamlit Community Cloud / generic hosts).

Delegates to the existing app. Kept import-safe: main() only runs when
executed as the Streamlit entry script.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for p in (str(ROOT / "src"), str(ROOT / "app")):
    if p not in sys.path:
        sys.path.insert(0, p)


def main() -> None:
    from app.app import main as run_app

    run_app()


if __name__ == "__main__":
    main()

