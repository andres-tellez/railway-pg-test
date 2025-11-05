# SMTP Variables Analysis

## Investigation Results

### Email Service Architecture

The email service (`src/services/email_service.py`) uses this priority:

1. **SendGrid REST API (Preferred)** - Lines 309-314
   - If `SENDGRID_API_KEY` is set → Uses SendGrid API
   - **SMTP variables are IGNORED** when SendGrid API is used

2. **SMTP Fallback** - Lines 317-323
   - Only used if `SENDGRID_API_KEY` is NOT set
   - Uses SMTP variables for connection

### SMTP Variables Usage

| Variable | Used For | Fallback Logic |
|----------|----------|----------------|
| `SMTP_HOST` | SMTP server connection | Only if SendGrid API not set |
| `SMTP_PORT` | SMTP server connection | Only if SendGrid API not set |
| `SMTP_USERNAME` | SMTP authentication | Only if SendGrid API not set |
| `SMTP_PASSWORD` | SMTP authentication | Only if SendGrid API not set |
| `SMTP_FROM_EMAIL` | Sender email | **FALLBACK** for `SENDGRID_FROM_EMAIL` |
| `SMTP_FROM_NAME` | Sender name | **FALLBACK** for `SENDGRID_FROM_NAME` |

### Code Evidence

**Line 55-57 (`get_sendgrid_config`):**
```python
from_email = os.getenv("SENDGRID_FROM_EMAIL") or os.getenv("SMTP_FROM_EMAIL")
from_name = os.getenv("SENDGRID_FROM_NAME") or os.getenv("SMTP_FROM_NAME", "SmartCoach")
```

**Line 309-314 (`send_email`):**
```python
# Try SendGrid API first (preferred - works on Railway)
sendgrid_config = EmailService.get_sendgrid_config()
if sendgrid_config["api_key"]:
    return EmailService.send_email_via_sendgrid_api(...)  # ← Returns here, SMTP never used
```

## Conclusion

### If `SENDGRID_API_KEY` is set (which you are using):

**❌ NOT NEEDED:**
- `SMTP_HOST` - Not used (SendGrid API used instead)
- `SMTP_PORT` - Not used (SendGrid API used instead)
- `SMTP_USERNAME` - Not used (SendGrid API used instead)
- `SMTP_PASSWORD` - Not used (SendGrid API used instead)

**⚠️ MAY BE USED (as fallback):**
- `SMTP_FROM_EMAIL` - Used if `SENDGRID_FROM_EMAIL` is NOT set
- `SMTP_FROM_NAME` - Used if `SENDGRID_FROM_NAME` is NOT set

### Recommendation

**If you have `SENDGRID_FROM_EMAIL` and `SENDGRID_FROM_NAME` set:**
- ✅ Can delete: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`
- ✅ Can delete: `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME` (if SendGrid vars are set)

**If you DON'T have `SENDGRID_FROM_EMAIL` and `SENDGRID_FROM_NAME` set:**
- ✅ Can delete: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`
- ⚠️ Keep: `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME` (used as fallback)

## Action Items

1. Check if `SENDGRID_FROM_EMAIL` and `SENDGRID_FROM_NAME` are set in Railway
2. If yes → Delete all 6 SMTP variables
3. If no → Keep `SMTP_FROM_EMAIL` and `SMTP_FROM_NAME`, delete the other 4
