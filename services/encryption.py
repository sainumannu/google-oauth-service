"""
Token encryption/decryption service
Uses Fernet symmetric encryption for secure token storage
"""
import os
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

class EncryptionService:
    """Service for encrypting and decrypting sensitive data"""
    
    def __init__(self):
        encryption_key = os.getenv("ENCRYPTION_KEY")
        
        if not encryption_key:
            logger.warning("ENCRYPTION_KEY not set - generating new key (tokens will be lost on restart!)")
            encryption_key = Fernet.generate_key().decode()
            logger.warning(f"Generated key: {encryption_key}")
            logger.warning("Add this to your .env file as ENCRYPTION_KEY")
        
        try:
            self.cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
            logger.info("Encryption service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            raise RuntimeError(f"Invalid ENCRYPTION_KEY: {e}")
    
    def encrypt(self, data: str) -> str:
        """Encrypt string data"""
        if not data:
            return ""
        try:
            return self.cipher.encrypt(data.encode()).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data"""
        if not encrypted_data:
            return ""
        try:
            return self.cipher.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise RuntimeError("Failed to decrypt token - key may have changed")

# Singleton instance
_encryption_service = None

def get_encryption_service() -> EncryptionService:
    """Get encryption service singleton"""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
