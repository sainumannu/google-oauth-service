"""
PramaIA Google OAuth2 Service
Centralized OAuth2 authentication for all Google services (Gmail, Drive, Calendar, etc.)
"""
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import logging

from routes import oauth_routes, token_routes
from services.database import init_database

# Load environment variables
load_dotenv()

# Logging configuration
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="PramaIA Google OAuth2 Service",
    description="Centralized OAuth2 authentication for Google services",
    version="1.0.0"
)

# CORS middleware
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(oauth_routes.router, prefix="/oauth", tags=["OAuth2 Flow"])
app.include_router(token_routes.router, prefix="/api", tags=["Token Management"])

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Starting PramaIA Google OAuth2 Service...")
    await init_database()
    logger.info(f"Service running on port {os.getenv('SERVICE_PORT', 8085)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "PramaIA Google OAuth2 Service",
        "version": "1.0.0"
    }

@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "PramaIA Google OAuth2 Service",
        "version": "1.0.0",
        "endpoints": {
            "authorize": "/oauth/authorize?userId={userId}&service={service}",
            "callback": "/oauth/callback (Google redirect)",
            "get_token": "/api/token/{userId}/{service}",
            "revoke": "/api/token/{userId}/{service} (DELETE)",
            "health": "/health"
        },
        "supported_services": [
            "gmail",
            "drive",
            "calendar",
            "meet",
            "sheets"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("SERVICE_PORT", 8085))
    host = os.getenv("SERVICE_HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
