"""
Shared SQL fragment for an activity row's local calendar date.

Requires FROM to include unqualified `start_date` and `timezone` columns (e.g.
`public.activities` alone). Backed by DB function `activity_local_date()`.
"""

ACTIVITY_LOCAL_DATE_SQL_FRAGMENT = "activity_local_date(start_date, timezone)"
