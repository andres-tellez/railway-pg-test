# Email SMTP Issue on Railway

## Problem

The scheduler is failing to send emails with the error:
```
[Errno 101] Network is unreachable
```

This occurs when trying to connect to `smtp.gmail.com` on port 587.

## Root Cause

**Railway is blocking outbound SMTP connections** from the container network. This is a common security practice in cloud platforms to prevent spam and abuse.

The error `[Errno 101]` means the network route to the SMTP server cannot be established - Railway's network firewall is likely blocking outbound connections on ports 587 and 465.

## Solutions

### Option 1: Use Port 465 with SSL (Try First) ✅

Gmail supports SSL on port 465, which might work better:

1. **Update Environment Variables** in Railway:
   ```
   SMTP_PORT=465
   ```

2. **Update SMTP Settings**:
   - The email service now automatically uses `SMTP_SSL` for port 465
   - No code changes needed (already implemented)

3. **Test**: Run the scheduler again and check logs

**Why this might work**: Some cloud platforms block STARTTLS (port 587) but allow direct SSL connections (port 465).

---

### Option 2: Use an SMTP Relay Service (Recommended for Production) ✅

Railway's network restrictions make direct SMTP unreliable. Use a dedicated email service:

#### A. SendGrid (Recommended)

1. **Sign up**: https://sendgrid.com (Free tier: 100 emails/day)

2. **Get API Key**:
   - SendGrid Dashboard → Settings → API Keys
   - Create API Key with "Mail Send" permission

3. **Update Environment Variables**:
   ```
   SMTP_HOST=smtp.sendgrid.net
   SMTP_PORT=587
   SMTP_USERNAME=apikey
   SMTP_PASSWORD=[your-sendgrid-api-key]
   SMTP_FROM_EMAIL=noreply@yourdomain.com
   SMTP_FROM_NAME=SmartCoach
   ```

4. **Pros**:
   - Reliable delivery
   - Email analytics
   - Better spam handling
   - Works with Railway

#### B. Mailgun

1. **Sign up**: https://www.mailgun.com (Free tier: 5,000 emails/month)

2. **Get SMTP Credentials**:
   - Mailgun Dashboard → Sending → SMTP Credentials

3. **Update Environment Variables**:
   ```
   SMTP_HOST=smtp.mailgun.org
   SMTP_PORT=587
   SMTP_USERNAME=[your-mailgun-username]
   SMTP_PASSWORD=[your-mailgun-password]
   ```

#### C. Amazon SES

1. **Set up AWS SES**
2. **Get SMTP Credentials**
3. **Update Environment Variables**:
   ```
   SMTP_HOST=email-smtp.[region].amazonaws.com
   SMTP_PORT=587
   SMTP_USERNAME=[ses-smtp-username]
   SMTP_PASSWORD=[ses-smtp-password]
   ```

---

### Option 3: Railway Private Networking (If Available)

Some Railway plans support private networking or SMTP proxies. Check Railway documentation for:
- Private networking features
- SMTP relay services
- Outbound connection allowlisting

---

### Option 4: Skip Email for Now (Temporary)

If email isn't critical, you can:
1. **Keep the scheduler running** - It completes successfully even if email fails
2. **Check logs** - All other tasks (metrics refresh, rebuild) work perfectly
3. **Fix email later** - Add an SMTP relay service when ready

---

## Testing

### Test SMTP Connection

Run the diagnostic script:

```bash
python src/scripts/test_smtp_connection.py
```

This will test:
- DNS resolution
- TCP connectivity to port 587
- TCP connectivity to port 465
- SMTP credentials

### Test Email Sending

You can test email sending manually:

```python
from src.services.email_service import EmailService

# Test email
EmailService.send_email(
    to_email="your-email@gmail.com",
    subject="Test Email",
    html_content="<h1>Test</h1><p>This is a test email.</p>"
)
```

---

## Current Status

✅ **Working:**
- Metrics refresh
- Weekly plan rebuild
- Scheduler timing
- All core functionality

❌ **Not Working:**
- Email notifications (due to Railway SMTP blocking)

---

## Recommended Next Steps

1. **Try Port 465 first** (quickest test):
   - Set `SMTP_PORT=465` in Railway
   - Test again

2. **If that doesn't work, set up SendGrid** (best for production):
   - Free tier is sufficient for most use cases
   - Reliable and works with Railway
   - Takes ~10 minutes to set up

3. **Update environment variables** in Railway:
   - Add SendGrid/Mailgun credentials
   - Test email sending

---

## References

- [Railway Networking Documentation](https://docs.railway.app/networking/)
- [SendGrid SMTP Setup](https://docs.sendgrid.com/for-developers/sending-email/getting-started-smtp)
- [Mailgun SMTP Setup](https://documentation.mailgun.com/en/latest/user_manual.html#sending-via-smtp)
