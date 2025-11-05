# FLASK_ENV Analysis

## Current Usage

`FLASK_ENV` is used in the following places:

1. **`src/app.py` lines 20-26**: Determines which `.env` file to load
   ```python
   raw_env_mode = os.environ.get("FLASK_ENV", "production")
   env_path = {
       "staging": ".env.staging",
       "production": ".env.prod",
   }.get(raw_env_mode, ".env.prod")
   load_dotenv(env_path, override=True)
   ```

2. **`run.py` lines 23-30**: Similar logic for local execution

3. **`alembic_env_backup.py`**: Used for Alembic migrations (backup file, not active)

4. **`src/scripts/verify_export_delete_e2e.py`**: Only for logging/debugging

## On Railway

### Current Behavior:
- Railway sets `FLASK_ENV=staging` in environment variables
- Code reads `FLASK_ENV` and tries to load `.env.staging` file
- **Problem**: `.env.staging` file doesn't exist on Railway (only environment variables exist)
- `load_dotenv()` silently fails if file doesn't exist (no error)
- Railway's environment variables are already set, so loading `.env.staging` doesn't matter

### If `FLASK_ENV` is Removed:
- Code defaults to `"production"` (line 21: `os.environ.get("FLASK_ENV", "production")`)
- Tries to load `.env.prod` (which also doesn't exist on Railway)
- **Result**: Same behavior - no `.env` file exists, environment variables are already set

## Conclusion

### ❌ **Not Strictly Needed on Railway**

**Reasons:**
1. No `.env` files exist on Railway - all variables are set directly in Railway's environment
2. `load_dotenv()` will silently fail when file doesn't exist (no error)
3. Default behavior (production) is fine if `FLASK_ENV` is missing
4. Not used for any application logic - only for selecting which `.env` file to load

**However:**
- ✅ **Harmless** - Doesn't hurt to keep it
- ✅ **Helpful for debugging** - Makes it clear which environment you're in
- ✅ **Used by Alembic** - `alembic_env_backup.py` uses it (though active `alembic/env.py` doesn't)

## Recommendation

**Option 1: Keep it (Recommended)**
- Harmless and provides clarity
- Helps with debugging/logging
- Low maintenance

**Option 2: Remove it**
- Not needed for functionality
- Cleaner environment variable list
- Must ensure Alembic migrations still work (check if active `alembic/env.py` uses it)

## Action

**Safe to remove** if you want to clean up, but **not necessary** to remove. It's purely cosmetic on Railway since no `.env` files exist.
