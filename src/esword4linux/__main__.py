"""Allow ``python -m esword4linux``."""

from .app import main

if __name__ == "__main__":
    raise SystemExit(main())
