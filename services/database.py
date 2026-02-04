"""
Database service for storing OAuth2 tokens
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, String, DateTime, Text
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Database setup
DATABASE_PATH = os.getenv("DATABASE_PATH", "storage/oauth_tokens.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_PATH}"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

class OAuthToken(Base):
    """OAuth token storage model"""
    __tablename__ = "oauth_tokens"
    
    id = Column(String, primary_key=True)  # {userId}_{service}
    user_id = Column(String, nullable=False, index=True)
    service = Column(String, nullable=False, index=True)
    access_token = Column(Text, nullable=False)  # Encrypted
    refresh_token = Column(Text, nullable=True)  # Encrypted
    token_type = Column(String, default="Bearer")
    expires_at = Column(DateTime, nullable=False)
    scopes = Column(Text, nullable=False)  # JSON array as string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

async def init_database():
    """Initialize database tables"""
    try:
        # Ensure storage directory exists
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info(f"Database initialized at {DATABASE_PATH}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

async def get_session() -> AsyncSession:
    """Get database session"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
