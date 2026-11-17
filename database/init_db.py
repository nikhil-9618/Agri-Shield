#!/usr/bin/env python3
"""Create the AgriShield tables.

SQLite (the default) needs no server: the script creates `backend/agrishield.db`.
For PostgreSQL set DATABASE_URL (and install `psycopg[binary]`), or apply
`database/schema.sql` directly with psql.

Usage:
    python database/init_db.py
    DATABASE_URL=postgresql+psycopg://user:pass@host/db python database/init_db.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Create AgriShield database tables")
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy URL; defaults to DATABASE_URL or sqlite:///./agrishield.db",
    )
    args = parser.parse_args()

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url

    try:
        from backend.app.db import Base, engine, init_db
        from backend.app import models  # noqa: F401  (register tables)
    except Exception as exc:
        print(f"Could not import the backend: {exc}", file=sys.stderr)
        print("Install backend requirements first: pip install -r backend/requirements.txt", file=sys.stderr)
        return 1

    init_db()
    print(f"database: {engine.url}")
    print("tables:  " + ", ".join(sorted(Base.metadata.tables)))
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
