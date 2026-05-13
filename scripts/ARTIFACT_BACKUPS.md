# Database backups via GitHub Actions **artifacts** (no B2 / S3)

This repo’s **Database Backup** workflow runs **`pg_dump` against production Postgres** and uploads the `.sql` file as a **workflow artifact**. It does **not** back up staging.

## Setup

1. **GitHub → repository → Settings → Secrets and variables → Actions**
2. Set **production** connection string **(required)** — use **one** of:
   - **`PRODUCTION_DATABASE_URL`** (recommended — name makes it clear this must be **prod**, e.g. Railway `db-prod`)
   - **`DATABASE_URL`** — only if this secret is **already** your **production** URL (never point it at staging for this workflow)

The **GitHub Actions runner** must be able to reach **production** Postgres (public URL / network rules per Railway).

## Schedule

- **Daily** at **02:00 UTC** — snapshot of **prod**
- **Manual:** Actions → **Database Backup** → **Run workflow**

## Retrieving a backup

1. Open the successful workflow run.
2. Scroll to **Artifacts**.
3. Download **`postgres-backup-prod-…`** (zip).
4. Unzip; you’ll have `backup_YYYYMMDD_HHMMSS.sql` (a **copy of production** at that time).

Artifacts follow **GitHub retention** (workflow sets **90 days** where the plan allows; org limits may apply).

## Restore

**What the artifact is:** a **production** snapshot. Restoring it **overwrites** the target database (dump uses `--clean`).

| Goal | Target DB |
|------|-----------|
| **Practice / drill** | **Staging** (or a disposable Postgres) — use `$STAGING_DATABASE_URL` so you don’t wipe prod. |
| **Real disaster recovery** | Production — only after a proven process and acceptance of downtime/data loss risk; same commands with **`$PRODUCTION_DATABASE_URL`**. |

Example **drill** (restore prod snapshot **into staging**):

```bash
cd railway-pg-test

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
