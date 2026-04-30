#!/usr/bin/env python3
"""
Run scripts/truncate_all_public_data.sql against a Postgres URL.

Prefers STAGING_DATABASE_URL (true Railway staging DB), then DATABASE_URL from .env.local.

Usage:
  # Add to .env.local (from Railway → Staging → Postgres variables):
  # STAGING_DATABASE_URL=postgresql://...

  python scripts/run_truncate_public.py

  # Or one-off:
  python scripts/run_truncate_public.py --url postgresql://user:pass@host:port/db?sslmode=require

Requires: psql on PATH
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_FILE = Path(__file__).resolve().parent / "truncate_all_public_data.sql"


def normalize_psql_url(url: str) -> str:
    url = url.strip().strip('"').strip("'")
    if url.startswith("postgresql+psycopg2://"):
        url = "postgresql://" + url.split("postgresql+psycopg2://", 1)[1]
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    return url


def main() -> int:
    parser = argparse.ArgumentParser(description="Truncate all public tables via psql")
    parser.add_argument(
        "--url",
        help="Postgres connection URL (overrides env)",
        default=None,
    )
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env.local", override=False)

    url = args.url or os.getenv("STAGING_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        print(
            "❌ No URL: set STAGING_DATABASE_URL or DATABASE_URL in .env.local,\n"
            "   or pass --url (copy from Railway → your Staging service → Postgres).",
            file=sys.stderr,
        )
        return 1

    url = normalize_psql_url(url)
    psql = shutil.which("psql")
    if not psql:
        print("❌ psql not found on PATH", file=sys.stderr)
        return 1

    if not SQL_FILE.is_file():
        print(f"❌ Missing {SQL_FILE}", file=sys.stderr)
        return 1

    print("Using:", url.split("@")[-1] if "@" in url else "(hidden url)")
    subprocess.run(
        [psql, url, "-v", "ON_ERROR_STOP=1", "-f", str(SQL_FILE)],
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
