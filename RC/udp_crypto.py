
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
import base64

class UDPCrypto:
    def __init__(self, shared_secret="ChatHub_UDP_Secret_2024"):
        """
        Initialize UDP encryption with a shared secret
        In production, use proper key exchange (Diffie-Hellman)
        """
        # Derive a 256-bit key from the shared secret
        salt = b'chathub_udp_salt_2024'  # Fixed salt (in production, negotiate this)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits
            salt=salt,
            iterations=100000,
        )
        self.key = kdf.derive(shared_secret.encode('utf-8'))
        self.aesgcm = AESGCM(self.key)
    
    def encrypt(self, plaintext):
        """
        Encrypt plaintext and return base64-encoded ciphertext with nonce
        Format: base64(nonce + ciphertext)
        """
        try:
            # Generate random 12-byte nonce (96 bits - recommended for GCM)
            nonce = os.urandom(12)
            
            # Encrypt the data
            ciphertext = self.aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
            
            # Combine nonce + ciphertext and encode to base64
            encrypted_data = nonce + ciphertext
            return base64.b64encode(encrypted_data).decode('ascii')
        except Exception as e:
            raise Exception(f"Encryption failed: {e}")
    
    def decrypt(self, encrypted_base64):
        """
        Decrypt base64-encoded ciphertext
        """
        try:
            # Decode from base64
            encrypted_data = base64.b64decode(encrypted_base64.encode('ascii'))
            
            # Extract nonce (first 12 bytes) and ciphertext (rest)
            nonce = encrypted_data[:12]
            ciphertext = encrypted_data[12:]
            
            # Decrypt
            plaintext = self.aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode('utf-8')
        except Exception as e:
            raise Exception(f"Decryption failed: {e}")
    
    def encrypt_message(self, message):
        """
        Encrypt a message and add encryption marker
        Format: ENC:<base64_encrypted_data>
        """
        encrypted = self.encrypt(message)
        return f"ENC:{encrypted}"
    
    def decrypt_message(self, encrypted_message):
        """
        Decrypt a message that starts with ENC:
        """
        if not encrypted_message.startswith("ENC:"):
            raise Exception("Not an encrypted message")
        
        encrypted_data = encrypted_message[4:]  # Remove "ENC:" prefix
        return self.decrypt(encrypted_data)