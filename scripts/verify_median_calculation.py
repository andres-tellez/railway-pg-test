#!/usr/bin/env python3
"""Verify SQL median matches Python median calculation."""

import sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=project_root / ".env.local", override=True)
sys.path.insert(0, str(project_root))

from src.db.db_session import get_session
from sqlalchemy import text
from datetime import datetime, timedelta
import statistics

user_id = "2e1c2581-619c-4a2a-a8b4-4dfc265e7789"
cutoff = datetime.now() - timedelta(weeks=6)

session = get_session()
try:
    # Get all paces
    query = text("""
        SELECT moving_time::float / conv_distance AS pace_sec_per_mile
        FROM activities
        WHERE user_id = :user_id
          AND type = 'Run'
          AND start_date >= :cutoff
          AND conv_distance >= 2.0
          AND moving_time IS NOT NULL
          AND moving_time > 0
          AND conv_distance > 0
          AND (moving_time::float / conv_distance) BETWEEN 360 AND 1200
        ORDER BY pace_sec_per_mile
    """)
    
    results = session.execute(query, {"user_id": user_id, "cutoff": cutoff}).fetchall()
    paces = [float(r.pace_sec_per_mile) for r in results]
    
    # Python median
    python_median = statistics.median(paces)
    
    # SQL median
    sql_query = text("""
        WITH valid_runs AS (
            SELECT moving_time::float / conv_distance AS pace_sec_per_mile
            FROM activities
            WHERE user_id = :user_id
              AND type = 'Run'
              AND start_date >= :cutoff
              AND conv_distance >= 2.0
              AND moving_time IS NOT NULL
              AND moving_time > 0
              AND conv_distance > 0
              AND (moving_time::float / conv_distance) BETWEEN 360 AND 1200
        )
        SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pace_sec_per_mile) AS median_pace
        FROM valid_runs
    """)
    
    sql_median = session.execute(sql_query, {"user_id": user_id, "cutoff": cutoff}).scalar()
    
    print("=" * 60)
    print("VERIFICATION: SQL vs Python Median")
    print("=" * 60)
    print(f"Total runs: {len(paces)}")
    print(f"Python median: {python_median:.1f} sec/mi")
    print(f"SQL median:    {float(sql_median):.1f} sec/mi")
    print(f"Difference:    {abs(python_median - float(sql_median)):.3f} sec/mi")
    print(f"Match:         {abs(python_median - float(sql_median)) < 0.1}")
    print("=" * 60)
    
    if abs(python_median - float(sql_median)) < 0.1:
        print("✅ SUCCESS: SQL and Python medians match!")
    else:
        print("❌ WARNING: Medians don't match!")
        
finally:
    session.close()

