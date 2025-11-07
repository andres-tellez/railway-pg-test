# Next Steps After Adding TOKEN_ENCRYPTION_KEY

**Date:** November 2025
**Status:** Ready to Complete

---

## ✅ Step 1: COMPLETE
You've added `TOKEN_ENCRYPTION_KEY` to:
- `.env.local` (local development)
- Railway staging backend (environment variables)

---

## ⏳ Step 2: Run Database Migration

You need to run the database migration to:
1. Add `revoked_at` column to `tokens` table
2. Create `auth_audit_log` table

### Option A: Using Railway Query Tab (Easiest)

1. Go to Railway → Your Database Service → **Query** tab
2. Copy the **entire contents** of `scripts/migrate_auth_best_practices.sql`
3. Paste into the query editor
4. Click **Run** or press `Ctrl+Enter`

The script is safe to run multiple times (it checks if things already exist).

### Option B: Using psql Command Line (Local)

If you have `psql` installed and want to run it locally:

```bash
# Set your DATABASE_URL first
export DATABASE_URL="your_database_url"

# Run the migration
psql $DATABASE_URL -f scripts/migrate_auth_best_practices.sql
```

**Note:** The SQL file uses PostgreSQL comments (`--`), so it works directly in Railway's Query tab or psql.

---

## ⏳ Step 3: Migrate Existing Tokens (If Any)

If you have existing tokens in your database, they need to be encrypted.

**Run the migration script:**
```bash
python scripts/migrate_tokens_to_encrypted.py
```

This script will:
- Read all existing tokens
- Encrypt them using the new encryption system
- Update the database

**Note:** If you don't have any existing tokens, you can skip this step.

---

## ⏳ Step 4: Test Everything

After completing the migrations:

1. **Restart your backend** (local and Railway)
   - This ensures the new code with encryption is running

2. **Test OAuth flow:**
   - Try connecting Strava account
   - Verify tokens are stored encrypted in database

3. **Test token refresh:**
   - Tokens should rotate on refresh
   - Check audit logs are created

4. **Verify encryption:**
   ```sql
   -- Check that tokens are encrypted (they should be longer strings)
   SELECT athlete_id, LENGTH(access_token) as token_length
   FROM tokens
   LIMIT 5;
   ```
   Encrypted tokens will be much longer than plain text tokens.

5. **Check audit logs:**
   ```sql
   -- View recent authentication events
   SELECT event_type, event_status, user_id, timestamp
   FROM auth_audit_log
   ORDER BY timestamp DESC
   LIMIT 10;
   ```

---

## Checklist

- [x] Added `TOKEN_ENCRYPTION_KEY` to `.env.local`
- [x] Added `TOKEN_ENCRYPTION_KEY` to Railway staging
- [ ] Run database migration (Railway Query tab or psql)
- [ ] Migrate existing tokens (if any)
- [ ] Restart backend (local)
- [ ] Restart backend (Railway staging)
- [ ] Test OAuth flow
- [ ] Verify tokens are encrypted in database
- [ ] Check audit logs are being created

---

## Troubleshooting

### "Failed to decrypt token"
- Make sure `TOKEN_ENCRYPTION_KEY` is set correctly
- Restart the backend after setting the key
- If you have existing tokens, run the migration script

### "Table auth_audit_log does not exist"
- Run the database migration SQL script in Railway Query tab
- Check that the table was created: `SELECT * FROM auth_audit_log LIMIT 1;`

### "Column revoked_at does not exist"
- Run the database migration SQL script in Railway Query tab
- Check that the column exists: `SELECT revoked_at FROM tokens LIMIT 1;`

---

## What's Next?

Once all steps are complete:
- ✅ CSRF protection is active (OAuth state validation)
- ✅ Tokens are encrypted at rest
- ✅ All auth events are logged to audit log
- ✅ Refresh tokens rotate on each use
- ✅ Tokens can be revoked immediately

Your authentication system now follows security best practices! 🎉
