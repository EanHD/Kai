"""Encryption utilities for data-at-rest protection using AES-256."""

import base64
import hashlib
import logging
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class EncryptionManager:
    """Manages AES-256 encryption for sensitive data."""

    def __init__(self, master_key: str):
        """Initialize encryption manager.

        Args:
            master_key: Master encryption key (from environment or user input)
        """
        self.master_key = master_key.encode()
        self.backend = default_backend()

    def _derive_key(self, salt: bytes) -> bytes:
        """Derive encryption key from master key using PBKDF2.

        Args:
            salt: Random salt for key derivation

        Returns:
            32-byte derived key for AES-256
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits
            salt=salt,
            iterations=100000,  # OWASP recommended minimum
            backend=self.backend,
        )
        return kdf.derive(self.master_key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext data.

        Args:
            plaintext: Data to encrypt

        Returns:
            Base64-encoded ciphertext with salt and IV
            Format: base64(salt:iv:ciphertext)
        """
        if not plaintext:
            return ""

        # Generate random salt and IV
        salt = os.urandom(16)
        iv = os.urandom(16)

        # Derive encryption key
        key = self._derive_key(salt)

        # Pad plaintext to block size (128 bits for AES)
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext.encode()) + padder.finalize()

        # Encrypt
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=self.backend)
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        # Combine salt:iv:ciphertext and encode
        combined = salt + iv + ciphertext
        encoded = base64.b64encode(combined).decode("utf-8")

        return encoded

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt encrypted data.

        Args:
            encrypted_data: Base64-encoded ciphertext with salt and IV

        Returns:
            Decrypted plaintext
        """
        if not encrypted_data:
            return ""

        try:
            # Decode and extract components
            combined = base64.b64decode(encrypted_data.encode("utf-8"))
            salt = combined[:16]
            iv = combined[16:32]
            ciphertext = combined[32:]

            # Derive decryption key
            key = self._derive_key(salt)

            # Decrypt
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=self.backend)
            decryptor = cipher.decryptor()
            padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

            # Unpad
            unpadder = padding.PKCS7(128).unpadder()
            plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()

            return plaintext.decode("utf-8")

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Failed to decrypt data - invalid key or corrupted data")

    @staticmethod
    def hash_key(key: str) -> str:
        """Generate SHA-256 hash of key for storage.

        Args:
            key: Key to hash

        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def generate_key() -> str:
        """Generate a secure random encryption key.

        Returns:
            Base64-encoded random key (32 bytes)
        """
        random_bytes = os.urandom(32)
        return base64.b64encode(random_bytes).decode("utf-8")


def encrypt_field(data: str, encryption_key: str) -> str:
    """Helper function to encrypt a single field.

    Args:
        data: Plaintext data
        encryption_key: Encryption key

    Returns:
        Encrypted data
    """
    manager = EncryptionManager(encryption_key)
    return manager.encrypt(data)


def decrypt_field(encrypted_data: str, encryption_key: str) -> str:
    """Helper function to decrypt a single field.

    Args:
        encrypted_data: Encrypted data
        encryption_key: Decryption key

    Returns:
        Decrypted plaintext
    """
    manager = EncryptionManager(encryption_key)
    return manager.decrypt(encrypted_data)
