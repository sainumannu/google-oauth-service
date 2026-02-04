"""
OAuth2 flow routes
Handles authorization and callback
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from services.oauth_manager import get_oauth_manager
from services.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/authorize")
async def authorize(
    userId: str = Query(..., description="User identifier"),
    service: str = Query(..., description="Service name (gmail, drive, calendar, etc.)")
):
    """
    Initiate OAuth2 authorization flow
    Redirects user to Google consent screen
    """
    try:
        oauth_manager = get_oauth_manager()
        auth_url = oauth_manager.get_authorization_url(userId, service)
        
        logger.info(f"Authorization initiated for user {userId}, service {service}")
        return RedirectResponse(url=auth_url)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Authorization failed: {e}")
        raise HTTPException(status_code=500, detail=f"Authorization failed: {str(e)}")

@router.get("/callback")
async def oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter"),
    session: AsyncSession = Depends(get_session)
):
    """
    OAuth2 callback endpoint
    Google redirects here after user authorizes
    """
    try:
        oauth_manager = get_oauth_manager()
        token_info = await oauth_manager.exchange_code_for_token(code, state, session)
        
        # Return success page
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authorization Successful</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                    text-align: center;
                    max-width: 500px;
                }}
                h1 {{ color: #4CAF50; margin-bottom: 20px; }}
                .success-icon {{ font-size: 64px; margin-bottom: 20px; }}
                .info {{ 
                    background: #f5f5f5; 
                    padding: 15px; 
                    border-radius: 5px; 
                    margin: 20px 0;
                    text-align: left;
                }}
                .info-item {{ 
                    margin: 8px 0;
                    font-size: 14px;
                }}
                .label {{ 
                    font-weight: bold; 
                    color: #666;
                }}
                .close-btn {{
                    background: #667eea;
                    color: white;
                    border: none;
                    padding: 12px 30px;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 16px;
                    margin-top: 20px;
                }}
                .close-btn:hover {{ background: #5568d3; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">✅</div>
                <h1>Authorization Successful!</h1>
                <p>You have successfully authorized PramaIA to access your Google {token_info['service']} account.</p>
                
                <div class="info">
                    <div class="info-item">
                        <span class="label">User ID:</span> {token_info['user_id']}
                    </div>
                    <div class="info-item">
                        <span class="label">Service:</span> {token_info['service']}
                    </div>
                    <div class="info-item">
                        <span class="label">Token expires:</span> {token_info['expires_at']}
                    </div>
                    <div class="info-item">
                        <span class="label">Scopes granted:</span> {len(token_info['scopes'])} permissions
                    </div>
                </div>
                
                <p style="color: #666; font-size: 14px;">
                    You can now close this window and return to your application.
                </p>
                
                <button class="close-btn" onclick="window.close()">Close Window</button>
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authorization Failed</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                    text-align: center;
                    max-width: 500px;
                }}
                h1 {{ color: #f5576c; margin-bottom: 20px; }}
                .error-icon {{ font-size: 64px; margin-bottom: 20px; }}
                .error-details {{
                    background: #ffe6e6;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 20px 0;
                    color: #c00;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="error-icon">❌</div>
                <h1>Authorization Failed</h1>
                <p>An error occurred during the authorization process.</p>
                <div class="error-details">
                    {str(e)}
                </div>
                <p style="color: #666; font-size: 14px;">
                    Please try again or contact support if the problem persists.
                </p>
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=error_html, status_code=500)
