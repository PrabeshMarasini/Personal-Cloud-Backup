import os
import base64
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import bytes, str
import logging

logger = logging.getLogger(__name__)

class EncryptionManager:
    def __init__(self, password: str):
        self.password = password.encode()
        self._fernet = None
    
    def _get_fernet(self, salt: bytes = None) -> Fernet:
        """Get Fernet instance with derived key"""
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.password))
        return Fernet(key), salt
    
    def encrypt_data(self, data: bytes) -> tuple[bytes, bytes]:
        """
        Encrypt data and return encrypted data with salt
        Returns: (encrypted_data, salt)
        """
        try:
            fernet, salt = self._get_fernet()
            encrypted_data = fernet.encrypt(data)
            logger.debug(f"Encrypted {len(data)} bytes to {len(encrypted_data)} bytes")
            return encrypted_data, salt
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt_data(self, encrypted_data: bytes, salt: bytes) -> bytes:
        """Decrypt data using the provided salt"""
        try:
            fernet, _ = self._get_fernet(salt)
            decrypted_data = fernet.decrypt(encrypted_data)
            logger.debug(f"Decrypted {len(encrypted_data)} bytes to {len(decrypted_data)} bytes")
            return decrypted_data
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    def encrypt_file(self, file_path: str) -> tuple[bytes, bytes]:
        """
        Encrypt file contents
        Returns: (encrypted_data, salt)
        """
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            return self.encrypt_data(data)
        except Exception as e:
            logger.error(f"File encryption failed for {file_path}: {e}")
            raise
    
    def decrypt_to_file(self, encrypted_data: bytes, salt: bytes, output_path: str) -> None:
        """Decrypt data and save to file"""
        try:
            decrypted_data = self.decrypt_data(encrypted_data, salt)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(decrypted_data)
            logger.info(f"Decrypted file saved to {output_path}")
        except Exception as e:
            logger.error(f"File decryption failed: {e}")
            raise
    
    @staticmethod
    def generate_file_hash(file_path: str) -> str:
        """Generate SHA-256 hash of file"""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Hash generation failed for {file_path}: {e}")
            raise
    
    @staticmethod
    def generate_data_hash(data: bytes) -> str:
        """Generate SHA-256 hash of data"""
        return hashlib.sha256(data).hexdigest()
    
    @staticmethod
    def generate_key() -> str:
        """Generate a random encryption key"""
        return base64.urlsafe_b64encode(os.urandom(32)).decode()

def create_encryption_manager(password: str = None) -> EncryptionManager:
    """Factory function to create encryption manager"""
    if not password:
        from config.config import config
        password = config.encryption_key
        if not password:
            raise ValueError("Encryption key not provided in configuration")
    
    return EncryptionManager(password)