# Google Places API Setup

This document explains how to set up Google Places API for location autocomplete in the plan creation form.

## Prerequisites

1. A Google Cloud Platform (GCP) account
2. A GCP project with billing enabled (Google Places API requires billing, but has a free tier)

## Setup Steps

### 1. Create API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (or create a new one)
3. Navigate to **APIs & Services** > **Credentials**
4. Click **Create Credentials** > **API Key**
5. Copy your API key

### 2. Enable Places API

1. Go to **APIs & Services** > **Library**
2. Search for "Places API"
3. Click on **Places API**
4. Click **Enable**

### 3. Restrict API Key (Recommended for Security)

1. Go back to **Credentials**
2. Click on your API key to edit it
3. Under **API restrictions**, select **Restrict key**
4. Choose **Places API** from the list
5. Under **Application restrictions**, you can optionally restrict by:
   - **HTTP referrers** (for web apps): Add your domain(s)
   - **IP addresses** (for server-side usage)
6. Click **Save**

### 4. Add API Key to Environment

Add the following to your `.env.local` file (or Railway environment variables):

```bash
VITE_GOOGLE_PLACES_API_KEY=your_api_key_here
```

**Note:** For production, add this as an environment variable in your hosting platform (e.g., Railway).

## Cost Information

- Google Places API has a **free tier**: $200 credit per month
- Autocomplete requests: **$2.83 per 1,000 requests** (first 1,000 free per month)
- The free tier typically covers ~70,000 autocomplete requests per month

## Fallback Behavior

If `VITE_GOOGLE_PLACES_API_KEY` is not set, the location field will still work as a regular text input. The autocomplete feature will simply be disabled.

## Testing

1. Start your development server: `npm run dev`
2. Navigate to the plan creation form
3. Start typing in the "Race Location" field
4. You should see city suggestions appear as you type

## Troubleshooting

- **No suggestions appearing**:

  - Check that the API key is correctly set in `.env.local`
  - Verify Places API is enabled in Google Cloud Console
  - Check browser console for errors
  - Ensure the API key is not restricted in a way that blocks your domain

- **"This API key is not authorized"**:

  - Verify Places API is enabled for your project
  - Check API key restrictions

- **CORS errors**:
  - Google Places API should handle CORS automatically
  - If issues persist, check API key restrictions

## Security Notes

- **Never commit your API key to git**
- Always use environment variables
- Restrict API keys to specific APIs and domains
- Monitor usage in Google Cloud Console to detect abuse
