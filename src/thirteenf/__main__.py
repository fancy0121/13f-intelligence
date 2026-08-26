"""Allow `python -m thirteenf <command>` (delegates to the CLI)."""

from thirteenf.cli import main

raise SystemExit(main())

