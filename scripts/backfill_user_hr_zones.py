#!/usr/bin/env python3
"""
Deprecated helper retained as a guard.

The legacy `user_hr_zones` table has been retired in favor of
`runner_zone_profiles`. Do not recreate or backfill `user_hr_zones`.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "This script is deprecated: user_hr_zones has been retired. "
        "Use runner_profile refresh/backfill flows instead."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
