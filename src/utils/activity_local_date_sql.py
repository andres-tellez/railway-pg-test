"""
Shared SQL for mapping an activity row's UTC start_date to a local calendar date.

Must be used only in queries whose FROM is `public.activities` alone (unqualified
`timezone` / `start_date` columns). Same semantics as GET /api/activities/.
"""

ACTIVITY_LOCAL_DATE_SQL_FRAGMENT = """
CASE
    WHEN timezone IS NOT NULL AND timezone LIKE '%America/%' THEN
        DATE((start_date AT TIME ZONE 'UTC') AT TIME ZONE
            SUBSTRING(timezone FROM POSITION(') ' IN timezone) + 2))
    WHEN timezone IS NOT NULL THEN
        DATE((start_date AT TIME ZONE 'UTC') AT TIME ZONE
            COALESCE(
                NULLIF(SUBSTRING(timezone FROM POSITION(') ' IN timezone) + 2), ''),
                'UTC'
            ))
    ELSE
        DATE(start_date)
END
""".strip()
