-- Truncate ALL heap tables in schema public (data only; tables stay).
-- Safe across environments: only truncates relations that actually exist (via pg_tables).
-- Materialized views are not in pg_tables; refresh them at the end if present.
--
-- Usage: run the ENTIRE file in one execution (Beekeeper: nothing selected, run all).
-- Tip: pause the API or avoid opening the app until done, or Strava sync can repopulate rows.
--
-- WARNING: Also clears alembic_version. Afterward run: alembic stamp head (or deploy migrations).

DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN
    SELECT quote_ident(tablename)::text AS t
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY tablename
  LOOP
    EXECUTE format('TRUNCATE TABLE %s RESTART IDENTITY CASCADE', r.t);
    RAISE NOTICE 'truncated %', r.t;
  END LOOP;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_matviews
    WHERE schemaname = 'public' AND matviewname = 'mv_athlete_metrics'
  ) THEN
    EXECUTE 'REFRESH MATERIALIZED VIEW mv_athlete_metrics';
    RAISE NOTICE 'refreshed mv_athlete_metrics';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_matviews
    WHERE schemaname = 'public' AND matviewname = 'mv_longest_runs'
  ) THEN
    EXECUTE 'REFRESH MATERIALIZED VIEW mv_longest_runs';
    RAISE NOTICE 'refreshed mv_longest_runs';
  END IF;
END $$;
