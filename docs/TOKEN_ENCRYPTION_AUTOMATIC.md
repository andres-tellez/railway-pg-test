# Token Encryption is Automatic

**Date:** November 2025
**Status:** ✅ Fully Automatic

---

## How It Works

Token encryption happens **automatically** via Python's `@hybrid_property` decorator in the `Token` model.

### When You Set a Token

```python
token = Token()
token.access_token = "plain_text_token_here"  # ← Automatically encrypted!
token.refresh_token = "plain_text_token_here"  # ← Automatically encrypted!
```

**What happens:**
1. You assign `token.access_token = "value"`
2. The `@hybrid_property` setter intercepts the assignment
3. It calls `encrypt_token(value)` automatically
4. Stores the encrypted value in `_encrypted_access_token` column

### When You Read a Token

```python
token = session.query(Token).first()
plain_token = token.access_token  # ← Automatically decrypted!
```

**What happens:**
1. You access `token.access_token`
2. The `@hybrid_property` getter intercepts the access
3. It calls `decrypt_token(_encrypted_access_token)` automatically
4. Returns the plain text token

---

## Code Location

See `src/db/models/tokens.py`:

```python
@hybrid_property
def access_token(self):
    """Decrypt access token when accessed."""
    from src.utils.token_encryption import decrypt_token
    return decrypt_token(self._encrypted_access_token)

@access_token.setter
def access_token(self, value):
    """Encrypt access token when set."""
    from src.utils.token_encryption import encrypt_token
    self._encrypted_access_token = encrypt_token(value)
```

---

## Where Encryption Happens Automatically

### 1. Token Storage (OAuth Callback)
```python
# src/services/token_service.py - store_tokens_from_callback()
token.access_token = token_data["access_token"]  # ← Auto-encrypted
token.refresh_token = token_data["refresh_token"]  # ← Auto-encrypted
```

### 2. Token Refresh
```python
# src/services/token_service.py - refresh_token_if_expired()
token.access_token = refreshed["access_token"]  # ← Auto-encrypted
token.refresh_token = refreshed["refresh_token"]  # ← Auto-encrypted
```

### 3. Direct Token Updates
Anywhere you do:
```python
token.access_token = "new_token"  # ← Always encrypted automatically
token.refresh_token = "new_token"  # ← Always encrypted automatically
```

---

## What You DON'T Need to Do

❌ **Don't manually encrypt:**
```python
# WRONG - Don't do this!
encrypted = encrypt_token("token")
token.access_token = encrypted  # This would double-encrypt!
```

✅ **Just assign directly:**
```python
# CORRECT - Do this!
token.access_token = "token"  # Automatically encrypted
```

---

## Database Storage

In the database, tokens are stored as encrypted strings in:
- `tokens.access_token` column (encrypted)
- `tokens.refresh_token` column (encrypted)

When you query the database directly:
```sql
SELECT access_token FROM tokens LIMIT 1;
-- Returns: encrypted string (~200+ characters)
```

When you access via Python:
```python
token = session.query(Token).first()
token.access_token  # Returns: plain text token (~40 characters)
```

---

## Verification

Run the test script:
```bash
python scripts/test_encryption_automatic.py
```

This verifies:
- ✅ Encryption/decryption works
- ✅ `TOKEN_ENCRYPTION_KEY` is set
- ✅ Encrypted tokens are longer than plain text

---

## Summary

**Tokens are encrypted automatically:**
- ✅ When you set `token.access_token = value` → automatically encrypted
- ✅ When you read `token.access_token` → automatically decrypted
- ✅ No code changes needed in your services
- ✅ Works transparently everywhere tokens are used

**You just need:**
1. ✅ `TOKEN_ENCRYPTION_KEY` set in environment
2. ✅ Database migration completed
3. ✅ Existing tokens migrated (if any)

That's it! Encryption is automatic going forward. 🎉
