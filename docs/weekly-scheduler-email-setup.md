# Weekly Scheduler & Email Notifications Setup

## Overview

The weekly scheduler runs every **Sunday at 6:00 PM Central** and performs three tasks:

1. **Metrics Refresh** - Refreshes materialized views and invalidates caches
2. **Weekly Plan Rebuild** - Rebuilds upcoming week's workouts for all active plans with pace adjustments
3. **Email Notifications** - Sends weekly update emails to users with workout changes and metrics validation

## Configuration

### Required Environment Variables

#### Database (Required)
```bash
DATABASE_URL=postgresql://user:password@host:port/database
```

#### SMTP Email Configuration (Optional but Recommended)
```bash
# SMTP Server Configuration
SMTP_HOST=smtp.gmail.com              # Default: smtp.gmail.com
SMTP_PORT=587                         # Default: 587 (TLS)
SMTP_USERNAME=your-email@gmail.com     # Required if sending emails
SMTP_PASSWORD=your-app-password        # Required if sending emails
SMTP_FROM_EMAIL=your-email@gmail.com  # Default: SMTP_USERNAME
SMTP_FROM_NAME=SmartCoach              # Default: SmartCoach
```

#### Scheduling Configuration (Optional)
```bash
USE_UTC_TIME=false                    # Default: false (uses Central Time)
```

### Email Setup Instructions

#### Gmail Setup
1. **Enable 2-Factor Authentication** on your Gmail account
2. **Generate an App Password**:
   - Go to: https://myaccount.google.com/apppasswords
   - Select "Mail" and "Other (Custom name)"
   - Enter "SmartCoach" as the name
   - Copy the 16-character password
3. **Set Environment Variables**:
   ```bash
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your-email@gmail.com
   SMTP_PASSWORD=xxxx xxxx xxxx xxxx  # Your 16-char app password
   ```

#### Other SMTP Providers
- **SendGrid**: Use `smtp.sendgrid.net` on port 587
- **Mailgun**: Use `smtp.mailgun.org` on port 587
- **Amazon SES**: Use your SES SMTP endpoint on port 587

## What Gets Emailed

Each user with an active training plan receives an email containing:

### 1. Workout Changes
- **Before/After comparison** for each workout in the upcoming week
- Changes tracked:
  - Description/Cues updates
  - Intensity adjustments
  - Segment count changes
  - Target HR zone updates

### 2. Metrics Dashboard Status
- **Success confirmation** when metrics refresh completed
- **Warning message** if metrics refresh encountered errors

### Email Template Features
- HTML formatted emails with responsive design
- Plain text fallback for email clients that don't support HTML
- Personalized with user's name
- Includes week number and start date
- Clear action items ("What's Next?")

## Behavior Without Email Configuration

If SMTP is not configured:
- ✅ Metrics refresh still runs
- ✅ Weekly rebuild still runs
- ⚠️ Email notifications are skipped (logged as warnings)
- ℹ️ All operations continue normally

## Testing

### Manual Trigger
To test the scheduler without waiting for Sunday:

```bash
# Run scheduler (will run on scheduled time)
python src/scripts/metrics_scheduler.py
```

### Test Email Service
```python
from src.services.email_service import EmailService

# Check if configured
if EmailService.is_configured():
    EmailService.send_weekly_update_email(
        to_email="test@example.com",
        user_name="Test User",
        week_num=5,
        week_start="2025-01-20",
        workout_changes=[
            {
                "date": "2025-01-20",
                "workout_type": "Easy Run",
                "miles": 4.0,
                "changes": [
                    {"field": "Description", "before": "Old", "after": "New"}
                ]
            }
        ],
        metrics_refresh_success=True,
        metrics_refresh_message="Metrics dashboard successfully refreshed."
    )
```

## Railway Deployment

The scheduler runs automatically as a worker process defined in `Procfile`:

```
cron_scheduler: python src/scripts/metrics_scheduler.py
```

### Setting Environment Variables in Railway

1. Go to Railway Dashboard → Your Project
2. Click **Variables** in left sidebar
3. Click **+ New Variable**
4. Add each SMTP variable:
   - `SMTP_HOST`
   - `SMTP_PORT`
   - `SMTP_USERNAME`
   - `SMTP_PASSWORD`
   - `SMTP_FROM_EMAIL` (optional)
   - `SMTP_FROM_NAME` (optional)

## Monitoring

### Log Messages
The scheduler logs all activities:

```
🔄 Step 1/3: Starting metrics refresh...
✅ Metrics refresh completed successfully
🔄 Step 2/3: Starting weekly plan rebuild...
📋 Found 3 active plan(s)
✅ Successfully rebuilt week 5 for plan 123
📧 Email notification sent to user@example.com
📊 Weekly rebuild summary: 3 rebuilt, 0 skipped, 0 errors, 3 emails sent, 0 emails failed
```

### Success Indicators
- ✅ All tasks completed successfully
- ✅ Emails sent count matches rebuilt plans count
- ✅ No errors in logs

### Error Handling
- ⚠️ Metrics refresh errors don't stop weekly rebuild
- ⚠️ Email failures are logged but don't stop processing
- ⚠️ Individual plan errors don't stop other plans from processing

## Troubleshooting

### Emails Not Sending
1. **Check SMTP configuration**:
   ```bash
   # Verify environment variables are set
   echo $SMTP_USERNAME
   echo $SMTP_PASSWORD
   ```

2. **Test email service**:
   ```python
   from src.services.email_service import EmailService
   print(f"Configured: {EmailService.is_configured()}")
   ```

3. **Check logs** for SMTP connection errors

### Scheduler Not Running
1. **Verify worker is running**:
   ```bash
   # Check Railway logs for scheduler process
   ```

2. **Check timezone**:
   - Default: Central Time
   - Override with `USE_UTC_TIME=true` for UTC

3. **Testing**: Scheduler runs automatically on schedule (Sunday at 6 PM Central)

### No Workout Changes Showing
- This is normal if workouts haven't changed
- Changes only tracked when:
  - Description/cues updated
  - Intensity adjusted
  - Segments modified
  - Target HR zones changed

## Schedule Details

- **Day**: Sunday
- **Time**: 6:00 PM Central (18:00)
- **Timezone**: Central Time (configurable via `USE_UTC_TIME`)
- **Frequency**: Weekly

## Security Notes

- **Never commit SMTP credentials** to version control
- **Use App Passwords** for Gmail (not your regular password)
- **Restrict SMTP access** to trusted IPs if possible
- **Monitor email sending** for abuse/spam reports
