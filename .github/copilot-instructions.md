# PramaIA Google OAuth2 Service - AI Coding Guidelines

## Architecture Overview

This is a **centralized OAuth2 authentication microservice** for Google APIs (Gmail, Drive, Calendar, Meet, Sheets). It acts as a token broker—plugins/clients request tokens via REST, and this service handles the full OAuth2 lifecycle including storage, encryption, and auto-refresh.

**Data Flow:**
1. Client → `/oauth/authorize?userId=X&service=gmail` → Google consent → `/oauth/callback`
2. Tokens encrypted with Fernet → stored in SQLite (`storage/oauth_tokens.db`)
3. Client → `/api/token/{userId}/{service}` → auto-refreshed decrypted token returned

**Key Design Decisions:**
- Token IDs follow `{userId}_{service}` composite key pattern
- All tokens encrypted at rest via `services/encryption.py` singleton
- Singleton pattern used for `OAuthManager` and `EncryptionService`
- Async SQLAlchemy with aiosqlite for non-blocking DB operations

## Project Structure

```
main.py                    # FastAPI app, startup, routes registration
routes/
  oauth_routes.py          # /oauth/* - authorization flow endpoints
  token_routes.py          # /api/*  - token CRUD operations
services/
  oauth_manager.py         # Core OAuth2 logic, GOOGLE_SCOPES config
  database.py              # SQLAlchemy models, async session factory
  encryption.py            # Fernet encryption singleton
storage/                   # SQLite database location (gitignored)
```

## Critical Patterns

### Adding New Google Services
Edit `GOOGLE_SCOPES` dict in [services/oauth_manager.py](services/oauth_manager.py#L22-L44):
```python
GOOGLE_SCOPES = {
    "gmail": ["https://www.googleapis.com/auth/gmail.send", ...],
    "new_service": ["https://www.googleapis.com/auth/new.scope"],  # Add here
}
```

### Database Session Handling
Always use dependency injection pattern with `Depends(get_session)`:
```python
@router.get("/endpoint")
async def handler(session: AsyncSession = Depends(get_session)):
    # session auto-managed
```

### Token Encryption Flow
Tokens are **always** encrypted before storage and decrypted on retrieval:
- `encryption.encrypt(token)` before DB write
- `encryption.decrypt(encrypted)` after DB read
- Never log or return raw tokens in error messages

## Development Commands

```powershell
# Start service (creates venv, installs deps, runs uvicorn)
.\start-oauth-service.ps1

# Manual start
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py

# Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Required Environment Variables

Configure in `.env` (copy from `.env.example`):
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` - From Google Cloud Console
- `ENCRYPTION_KEY` - Fernet key (losing this invalidates all stored tokens)
- `GOOGLE_REDIRECT_URI` - Must match Google Console (default: `http://localhost:8085/oauth/callback`)
- `SERVICE_PORT` - Default 8085

## API Endpoints Quick Reference

| Endpoint | Purpose |
|----------|---------|
| `GET /oauth/authorize?userId=X&service=Y` | Initiates OAuth flow |
| `GET /oauth/callback` | Google redirect target (internal) |
| `GET /api/token/{userId}/{service}` | Get valid token (auto-refreshes) |
| `DELETE /api/token/{userId}/{service}` | Revoke token |
| `GET /api/tokens/{userId}` | List user's authorized services |
| `GET /health` | Health check |
| `GET /docs` | Swagger UI |

## Testing Notes

- Use `http://localhost:8085/docs` for interactive API testing
- Test OAuth flow: `/oauth/authorize?userId=test_user&service=gmail`
- Tokens require valid Google Cloud OAuth credentials to work
