"""
Token management routes
Get, refresh, and revoke tokens
"""
from fastapi import APIRouter, HTTPException, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from services.oauth_manager import get_oauth_manager
from services.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/token/{userId}/{service}")
async def get_token(
    userId: str = Path(..., description="User identifier"),
    service: str = Path(..., description="Service name"),
    session: AsyncSession = Depends(get_session)
):
    """
    Get valid access token for user and service
    Automatically refreshes if expired
    """
    try:
        oauth_manager = get_oauth_manager()
        token = await oauth_manager.get_valid_token(userId, service, session)
        
        if not token:
            raise HTTPException(
                status_code=404,
                detail=f"No valid token found for user {userId} and service {service}. Please authorize first."
            )
        
        return {
            "access_token": token,
            "token_type": "Bearer",
            "user_id": userId,
            "service": service
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get token: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve token: {str(e)}")

@router.delete("/token/{userId}/{service}")
async def revoke_token(
    userId: str = Path(..., description="User identifier"),
    service: str = Path(..., description="Service name"),
    session: AsyncSession = Depends(get_session)
):
    """
    Revoke and delete stored token
    """
    try:
        oauth_manager = get_oauth_manager()
        success = await oauth_manager.revoke_token(userId, service, session)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"No token found for user {userId} and service {service}"
            )
        
        return {
            "success": True,
            "message": f"Token revoked for user {userId}, service {service}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke token: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to revoke token: {str(e)}")

@router.get("/tokens/{userId}")
async def list_user_tokens(
    userId: str = Path(..., description="User identifier"),
    session: AsyncSession = Depends(get_session)
):
    """
    List all authorized services for a user
    """
    try:
        from sqlalchemy import select
        from services.database import OAuthToken
        
        result = await session.execute(
            select(OAuthToken).where(OAuthToken.user_id == userId)
        )
        tokens = result.scalars().all()
        
        return {
            "user_id": userId,
            "authorized_services": [
                {
                    "service": token.service,
                    "expires_at": token.expires_at.isoformat(),
                    "has_refresh_token": bool(token.refresh_token),
                    "created_at": token.created_at.isoformat(),
                    "updated_at": token.updated_at.isoformat()
                }
                for token in tokens
            ],
            "total_services": len(tokens)
        }
        
    except Exception as e:
        logger.error(f"Failed to list tokens: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list tokens: {str(e)}")
