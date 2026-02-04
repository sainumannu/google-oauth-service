---
title: "Google OAuth2 Service Setup Guide"
description: "Complete guide for setting up and using the PramaIA Google OAuth2 Service"
author: "PramaIA"
tags: ["oauth2", "google", "authentication", "setup"]
difficulty: "intermediate"
estimatedReadTime: "15 min"
---

# PramaIA Google OAuth2 Service

Centralized OAuth2 authentication service for all Google services (Gmail, Drive, Calendar, Meet, Sheets).

## Features

- ✅ **Multi-service support**: Gmail, Drive, Calendar, Meet, Sheets
- ✅ **Multi-user**: Each user has their own OAuth2 tokens
- ✅ **Secure storage**: Tokens encrypted with Fernet symmetric encryption
- ✅ **Auto-refresh**: Expired tokens automatically refreshed
- ✅ **RESTful API**: Easy integration with any application
- ✅ **Token management**: List, revoke, and monitor user tokens

## Architecture

```
┌─────────────────┐
│  Gmail Plugin   │───┐
└─────────────────┘   │
┌─────────────────┐   │    ┌──────────────────────┐
│  Drive Plugin   │───┼───▶│ OAuth2 Service:8085  │
└─────────────────┘   │    │  - Token Storage     │
┌─────────────────┐   │    │  - Auto Refresh      │
│ Calendar Plugin │───┘    │  - Encryption        │
└─────────────────┘        └──────────────────────┘
                                      │
                                      ▼
                            ┌──────────────────┐
                            │  Google APIs     │
                            │  - Gmail         │
                            │  - Drive         │
                            │  - Calendar      │
                            └──────────────────┘
```

## Setup

### 1. Google Cloud Console Configuration

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable APIs:
   - Gmail API
   - Google Drive API
   - Google Calendar API
   - (Add others as needed)

4. Create OAuth2 Credentials:
   - Go to **APIs & Services > Credentials**
   - Click **Create Credentials > OAuth 2.0 Client ID**
   - Application type: **Web application**
   - Authorized redirect URIs: `http://localhost:8085/oauth/callback`
   - Copy **Client ID** and **Client Secret**

### 2. Environment Configuration

```bash
cd PramaIA-GoogleOAuth-Service
cp .env.example .env
```

Edit `.env`:

```env
# From Google Cloud Console
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# Generate encryption key
# Run: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-generated-key

# Service configuration
SERVICE_PORT=8085
SERVICE_HOST=0.0.0.0
LOG_LEVEL=INFO

# Database
DATABASE_PATH=storage/oauth_tokens.db

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001,http://localhost:8080
```

### 3. Start Service

```powershell
.\start-oauth-service.ps1
```

The service will be available at:
- API: http://localhost:8085
- Docs: http://localhost:8085/docs
- Health: http://localhost:8085/health

## Usage

### 1. User Authorization Flow

**Step 1**: Redirect user to authorization URL

```http
GET http://localhost:8085/oauth/authorize?userId=user123&service=gmail
```

This redirects to Google consent screen.

**Step 2**: User authorizes and is redirected back

Google redirects to `/oauth/callback` with authorization code. Service automatically:
- Exchanges code for tokens
- Encrypts and stores tokens
- Shows success page to user

**Step 3**: Use token in your plugin

```python
import httpx

async def send_email(user_id: str, message: dict):
    # Get token from OAuth2 service
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8085/api/token/{user_id}/gmail"
        )
        token_data = response.json()
        access_token = token_data["access_token"]
    
    # Use token to call Gmail API
    # ...
```

### 2. Get Valid Token

```http
GET http://localhost:8085/api/token/{userId}/{service}
```

**Response:**
```json
{
  "access_token": "ya29.a0AfH6SMB...",
  "token_type": "Bearer",
  "user_id": "user123",
  "service": "gmail"
}
```

Token is automatically refreshed if expired.

### 3. List User's Authorized Services

```http
GET http://localhost:8085/api/tokens/{userId}
```

**Response:**
```json
{
  "user_id": "user123",
  "authorized_services": [
    {
      "service": "gmail",
      "expires_at": "2026-01-28T15:30:00",
      "has_refresh_token": true,
      "created_at": "2026-01-28T14:30:00",
      "updated_at": "2026-01-28T14:30:00"
    }
  ],
  "total_services": 1
}
```

### 4. Revoke Token

```http
DELETE http://localhost:8085/api/token/{userId}/{service}
```

**Response:**
```json
{
  "success": true,
  "message": "Token revoked for user user123, service gmail"
}
```

## Supported Services

| Service | Scopes |
|---------|--------|
| **gmail** | `gmail.send`, `gmail.readonly`, `gmail.modify` |
| **drive** | `drive.file`, `drive.readonly` |
| **calendar** | `calendar`, `calendar.events` |
| **meet** | `calendar.events`, `meetings.space.created` |
| **sheets** | `spreadsheets`, `spreadsheets.readonly` |

## Plugin Integration

### Example: Gmail Plugin with OAuth2

```python
# plugins/gmail-plugin/src/resolvers/send_email.py
import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64

class SendEmail:
    async def process(self, context):
        inputs = context.get('inputs', {})
        config = context.get('config', {})
        user_context = context.get('context', {})
        
        user_id = user_context.get('userId')
        recipient = inputs.get('recipient')
        subject = inputs.get('subject')
        body = inputs.get('body')
        
        # Get OAuth2 token from service
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:8085/api/token/{user_id}/gmail"
            )
            
            if response.status_code != 200:
                raise RuntimeError(
                    f"User {user_id} not authorized for Gmail. "
                    f"Please authorize at: http://localhost:8085/oauth/authorize?userId={user_id}&service=gmail"
                )
            
            token_data = response.json()
            access_token = token_data["access_token"]
        
        # Create credentials
        credentials = Credentials(token=access_token)
        
        # Build Gmail API service
        service = build('gmail', 'v1', credentials=credentials)
        
        # Create message
        message = MIMEText(body)
        message['to'] = recipient
        message['subject'] = subject
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Send
        result = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        
        return {
            "success": True,
            "message_id": result['id'],
            "status": "sent"
        }
```

## Security

- ✅ **Encrypted storage**: All tokens encrypted with Fernet
- ✅ **HTTPS only in production**: Configure proper SSL/TLS
- ✅ **Scoped access**: Only request necessary permissions
- ✅ **User-controlled**: Users can revoke access anytime
- ✅ **No password storage**: OAuth2 flow, no user credentials stored

### Production Deployment

**Important for production:**

1. **Use HTTPS**: Update `GOOGLE_REDIRECT_URI` to HTTPS URL
2. **Strong encryption key**: Generate secure key and store safely
3. **Database backup**: Regular backups of `oauth_tokens.db`
4. **Environment variables**: Never commit `.env` to version control
5. **Authorized domains**: Configure in Google Cloud Console

## Troubleshooting

### "Invalid redirect_uri"
- Check Google Cloud Console authorized redirect URIs
- Ensure `GOOGLE_REDIRECT_URI` in `.env` matches exactly

### "No token found"
- User needs to authorize first: visit `/oauth/authorize`
- Check logs for authorization errors

### "Token refresh failed"
- Refresh token may be missing (user didn't grant offline access)
- Re-authorize with `prompt=consent` to get new refresh token

### "Decryption failed"
- `ENCRYPTION_KEY` changed - tokens encrypted with old key can't be decrypted
- Users need to re-authorize

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/oauth/authorize` | Start OAuth2 flow |
| GET | `/oauth/callback` | OAuth2 callback (Google redirect) |
| GET | `/api/token/{userId}/{service}` | Get valid token |
| DELETE | `/api/token/{userId}/{service}` | Revoke token |
| GET | `/api/tokens/{userId}` | List user's tokens |
| GET | `/health` | Health check |
| GET | `/` | Service info |

### Query Parameters

**`/oauth/authorize`:**
- `userId` (required): User identifier
- `service` (required): Service name (gmail, drive, calendar, etc.)

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Run service
python main.py

# Run with auto-reload (development)
uvicorn main:app --reload --port 8085
```

## License

MIT License - Part of PramaIA Project
