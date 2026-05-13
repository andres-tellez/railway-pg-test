# Database backups via GitHub Actions **artifacts** (no B2 / S3)

This repo’s **Database Backup** workflow (`.github/workflows/database-backup.yml`) runs `pg_dump` and uploads the `.sql` file as a **workflow artifact**.

## Setup

1. **GitHub → repository → Settings → Secrets and variables → Actions**
2. Add **`DATABASE_URL`** — your production Postgres connection URL.
   - The **GitHub Actions runner** must be able to reach the database (public `DATABASE_URL` / network rules as Railway documents).

## Schedule

- **Daily** at **02:00 UTC**
- **Manual:** Actions → **Database Backup** → **Run workflow**

## Retrieving a backup

1. Open the successful workflow run.
2. Scroll to **Artifacts**.
3. Download **`postgres-backup-…`** (zip).
4. Unzip; you’ll have `backup_YYYYMMDD_HHMMSS.sql`.

Artifacts follow **GitHub retention** (workflow sets **90 days** where the plan allows; org limits may apply).

## Restore (staging first)

**Warning:** dumps are created with `pg_dump --clean`; restore **drops objects** in the target database. Use **staging** or a **throwaway** DB for drills.

With **PostgreSQL client** (`psql`) and repo checkout:

```bash
cd railway-pg-test

# Path to the .sql file you unzipped from the artifact:
python scripts/restore_database.py \
  --backup /path/to/backup_20260115_020301.sql \
  --database-url "$STAGING_DATABASE_URL" \
  --confirm
```

Or with `psql` directly:

```bash
psql "$STAGING_DATABASE_URL" -f /path/to/backup_20260115_020301.sql
```

## Legacy: B2 / S3

Older docs (`BACKUP_SETUP.md`) describe **B2** and **S3** uploads. The current **default workflow** uses **artifacts only**. To use B2/S3 again, restore a previous `database-backup.yml` from git history or add a separate workflow.
