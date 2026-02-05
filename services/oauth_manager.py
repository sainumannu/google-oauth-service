"""
OAuth2 Manager - Core OAuth2 flow logic
Handles authorization, token exchange, refresh, and revocation
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database import OAuthToken, get_session
from services.encryption import get_encryption_service

logger = logging.getLogger(__name__)

# Google OAuth2 scopes for different services
GOOGLE_SCOPES = {
    "gmail": [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify"
    ],
    "drive": [
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive.readonly"
    ],
    "calendar": [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events"
    ],
    "meet": [
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/meetings.space.created"
    ],
    "sheets": [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/spreadsheets.readonly"
    ]
}

class OAuthManager:
    """OAuth2 flow manager for Google services"""
    
    def __init__(self):
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
        self.encryption = get_encryption_service()
        
        if not all([self.client_id, self.client_secret, self.redirect_uri]):
            raise RuntimeError("Missing Google OAuth2 configuration. Check .env file.")
        
        logger.info("OAuth Manager initialized")
    
    def get_authorization_url(self, user_id: str, service: str, state: Optional[str] = None) -> str:
        """
        Generate Google OAuth2 authorization URL
        
        Args:
            user_id: Unique user identifier
            service: Service name (gmail, drive, calendar, etc.)
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL for user to visit
        """
        if service not in GOOGLE_SCOPES:
            raise ValueError(f"Unsupported service: {service}. Supported: {list(GOOGLE_SCOPES.keys())}")
        
        scopes = GOOGLE_SCOPES[service]
        
        # Create state with user_id and service
        if not state:
            state = json.dumps({"user_id": user_id, "service": service})
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=scopes,
            redirect_uri=self.redirect_uri
        )
        
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state,
            prompt='consent'  # Force consent to get refresh token
        )
        
        logger.info(f"Generated authorization URL for user {user_id}, service {service}")
        return auth_url
    
    async def exchange_code_for_token(self, code: str, state: str, session: AsyncSession) -> Dict:
        """
        Exchange authorization code for access/refresh tokens
        
        Args:
            code: Authorization code from Google
            state: State parameter containing user_id and service
            session: Database session
            
        Returns:
            Token information dict
        """
        try:
            # Parse state
            state_data = json.loads(state)
            user_id = state_data["user_id"]
            service = state_data["service"]
            scopes = GOOGLE_SCOPES[service]
            
            # Create flow and exchange code
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.redirect_uri]
                    }
                },
                scopes=scopes,
                redirect_uri=self.redirect_uri,
                autogenerate_code_verifier=True
            )
            
            # Disable scope verification - Google may return additional scopes 
            # from previously authorized services
            import os
            os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
            
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # Calculate expiration
            expires_at = datetime.utcnow() + timedelta(seconds=credentials.expiry.timestamp() - datetime.utcnow().timestamp() if credentials.expiry else 3600)
            
            # Encrypt tokens
            encrypted_access_token = self.encryption.encrypt(credentials.token)
            encrypted_refresh_token = self.encryption.encrypt(credentials.refresh_token) if credentials.refresh_token else None
            
            # Store in database
            token_id = f"{user_id}_{service}"
            
            # Check if token already exists
            result = await session.execute(select(OAuthToken).where(OAuthToken.id == token_id))
            existing_token = result.scalar_one_or_none()
            
            if existing_token:
                # Update existing token
                existing_token.access_token = encrypted_access_token
                existing_token.refresh_token = encrypted_refresh_token
                existing_token.expires_at = expires_at
                existing_token.scopes = json.dumps(scopes)
                existing_token.updated_at = datetime.utcnow()
            else:
                # Create new token
                oauth_token = OAuthToken(
                    id=token_id,
                    user_id=user_id,
                    service=service,
                    access_token=encrypted_access_token,
                    refresh_token=encrypted_refresh_token,
                    token_type="Bearer",
                    expires_at=expires_at,
                    scopes=json.dumps(scopes)
                )
                session.add(oauth_token)
            
            await session.commit()
            
            logger.info(f"Token stored for user {user_id}, service {service}")
            
            return {
                "user_id": user_id,
                "service": service,
                "scopes": scopes,
                "expires_at": expires_at.isoformat(),
                "has_refresh_token": bool(credentials.refresh_token)
            }
            
        except Exception as e:
            logger.error(f"Failed to exchange code for token: {e}")
            raise RuntimeError(f"Token exchange failed: {e}")
    
    async def get_valid_token(self, user_id: str, service: str, session: AsyncSession) -> Optional[str]:
        """
        Get valid access token, refreshing if necessary
        
        Args:
            user_id: User identifier
            service: Service name
            session: Database session
            
        Returns:
            Valid access token or None if not found/failed
        """
        token_id = f"{user_id}_{service}"
        
        # Fetch token from database
        result = await session.execute(select(OAuthToken).where(OAuthToken.id == token_id))
        oauth_token = result.scalar_one_or_none()
        
        if not oauth_token:
            logger.warning(f"No token found for user {user_id}, service {service}")
            return None
        
        # Check if token is expired
        if datetime.utcnow() >= oauth_token.expires_at:
            logger.info(f"Token expired for user {user_id}, service {service} - refreshing...")
            
            if not oauth_token.refresh_token:
                logger.error(f"No refresh token available for user {user_id}, service {service}")
                return None
            
            # Refresh token
            try:
                refreshed = await self._refresh_token(oauth_token, session)
                if not refreshed:
                    return None
                # Reload token after refresh
                await session.refresh(oauth_token)
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                return None
        
        # Decrypt and return access token
        try:
            return self.encryption.decrypt(oauth_token.access_token)
        except Exception as e:
            logger.error(f"Failed to decrypt token: {e}")
            return None
    
    async def _refresh_token(self, oauth_token: OAuthToken, session: AsyncSession) -> bool:
        """
        Refresh an expired access token
        
        Args:
            oauth_token: OAuthToken object
            session: Database session
            
        Returns:
            True if refresh successful
        """
        try:
            # Decrypt refresh token
            refresh_token = self.encryption.decrypt(oauth_token.refresh_token)
            scopes = json.loads(oauth_token.scopes)
            
            # Create credentials object
            credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=scopes
            )
            
            # Refresh
            from google.auth.transport.requests import Request
            credentials.refresh(Request())
            
            # Update database
            oauth_token.access_token = self.encryption.encrypt(credentials.token)
            oauth_token.expires_at = datetime.utcnow() + timedelta(seconds=3600)
            oauth_token.updated_at = datetime.utcnow()
            
            await session.commit()
            
            logger.info(f"Token refreshed for user {oauth_token.user_id}, service {oauth_token.service}")
            return True
            
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return False
    
    async def revoke_token(self, user_id: str, service: str, session: AsyncSession) -> bool:
        """
        Revoke and delete stored token
        
        Args:
            user_id: User identifier
            service: Service name
            session: Database session
            
        Returns:
            True if revoked successfully
        """
        token_id = f"{user_id}_{service}"
        
        result = await session.execute(select(OAuthToken).where(OAuthToken.id == token_id))
        oauth_token = result.scalar_one_or_none()
        
        if not oauth_token:
            logger.warning(f"No token to revoke for user {user_id}, service {service}")
            return False
        
        # Delete from database
        await session.delete(oauth_token)
        await session.commit()
        
        logger.info(f"Token revoked for user {user_id}, service {service}")
        return True

# Singleton instance
_oauth_manager = None

def get_oauth_manager() -> OAuthManager:
    """Get OAuth manager singleton"""
    global _oauth_manager
    if _oauth_manager is None:
        _oauth_manager = OAuthManager()
    return _oauth_manager
