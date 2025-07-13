# File: api_manager.py
# Path: /core/api_manager.py

import os
import json
import logging
from typing import Optional
import keyring
from cryptography.fernet import Fernet
import base64
from pathlib import Path

logger = logging.getLogger(__name__)

class APIKeyManager:
    """Secure API key management for non-technical users"""
    
    SERVICE_NAME = "AIVideoTool"
    KEY_NAME = "openai_api_key"
    
    def __init__(self):
        self.config_dir = self._get_config_dir()
        self.config_file = os.path.join(self.config_dir, "config.json")
        self._ensure_config_dir()
    
    def _get_config_dir(self) -> str:
        """Get platform-specific config directory"""
        home = Path.home()
        
        if os.name == 'nt':  # Windows
            config_dir = os.path.join(os.environ.get('APPDATA', home), 'AIVideoTool')
        elif os.name == 'posix':
            if 'darwin' in os.sys.platform:  # macOS
                config_dir = os.path.join(home, 'Library', 'Application Support', 'AIVideoTool')
            else:  # Linux
                config_dir = os.path.join(home, '.config', 'AIVideoTool')
        else:
            config_dir = os.path.join(home, '.AIVideoTool')
        
        return config_dir
    
    def _ensure_config_dir(self):
        """Ensure config directory exists"""
        os.makedirs(self.config_dir, exist_ok=True)
    
    def set_api_key(self, api_key: str) -> bool:
        """Store API key securely"""
        try:
            # Try system keyring first (most secure)
            try:
                keyring.set_password(self.SERVICE_NAME, self.KEY_NAME, api_key)
                logger.info("API key stored in system keyring")
                return True
            except Exception as e:
                logger.warning(f"Keyring storage failed, using fallback: {str(e)}")
            
            # Fallback to encrypted file storage
            self._store_encrypted_key(api_key)
            return True
            
        except Exception as e:
            logger.error(f"Failed to store API key: {str(e)}")
            return False
    
    def get_api_key(self) -> Optional[str]:
        """Retrieve API key"""
        try:
            # Try system keyring first
            try:
                key = keyring.get_password(self.SERVICE_NAME, self.KEY_NAME)
                if key:
                    return key
            except Exception:
                pass
            
            # Try encrypted file
            key = self._get_encrypted_key()
            if key:
                return key
            
            # Try environment variable
            key = os.environ.get('OPENAI_API_KEY')
            if key:
                logger.info("Using API key from environment variable")
                return key
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve API key: {str(e)}")
            return None
    
    def has_api_key(self) -> bool:
        """Check if API key is configured"""
        return self.get_api_key() is not None
    
    def _get_encryption_key(self) -> bytes:
        """Get or create encryption key for file storage"""
        key_file = os.path.join(self.config_dir, '.key')
        
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            # Set restrictive permissions on Unix-like systems
            if os.name != 'nt':
                os.chmod(key_file, 0o600)
            return key
    
    def _store_encrypted_key(self, api_key: str):
        """Store API key in encrypted file"""
        cipher = Fernet(self._get_encryption_key())
        encrypted_key = cipher.encrypt(api_key.encode())
        
        config = {
            'encrypted_api_key': base64.b64encode(encrypted_key).decode()
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f)
        
        # Set restrictive permissions
        if os.name != 'nt':
            os.chmod(self.config_file, 0o600)
        
        logger.info("API key stored in encrypted file")
    
    def _get_encrypted_key(self) -> Optional[str]:
        """Retrieve API key from encrypted file"""
        if not os.path.exists(self.config_file):
            return None
        
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            encrypted_key = base64.b64decode(config.get('encrypted_api_key', ''))
            cipher = Fernet(self._get_encryption_key())
            api_key = cipher.decrypt(encrypted_key).decode()
            return api_key
        except Exception as e:
            logger.error(f"Failed to decrypt API key: {str(e)}")
            return None
    
    def remove_api_key(self):
        """Remove stored API key"""
        try:
            # Remove from keyring
            try:
                keyring.delete_password(self.SERVICE_NAME, self.KEY_NAME)
            except Exception:
                pass
            
            # Remove config file
            if os.path.exists(self.config_file):
                os.remove(self.config_file)
            
            logger.info("API key removed")
        except Exception as e:
            logger.error(f"Failed to remove API key: {str(e)}")
    
    @staticmethod
    def validate_api_key(api_key: str) -> bool:
        """Validate OpenAI API key format"""
        # OpenAI keys start with 'sk-' and are typically 51 characters
        if not api_key or not api_key.startswith('sk-'):
            return False
        if len(api_key) < 20:  # Reasonable minimum length
            return False
        return True