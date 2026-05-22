"""
HybridCryptoService — RSA-OAEP + AES-256-GCM hybrid encryption/decryption.

Wire format (base64-decoded bytes):
  [256 bytes]  RSA-OAEP encrypted AES-256 key
  [12 bytes]   AES-GCM IV (nonce)
  [N bytes]    AES-GCM ciphertext + 16-byte GCM auth tag (appended by the library)

Why hybrid?
  RSA-2048 with OAEP can only encrypt ~245 bytes. Our JSON payload exceeds that.
  So we generate a fresh AES-256 key per packet, encrypt the payload with AES-GCM
  (fast + authenticated), and wrap just the AES key with RSA.

Why AES-GCM?
  It's authenticated encryption: flipping any byte in the ciphertext causes
  decryption to throw InvalidTag — the server can never be tricked into
  processing tampered data.
"""

import os
import hashlib
import base64
import json

from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from crypto.server_key import ServerKeyHolder


RSA_KEY_BYTES = 256   # 2048-bit RSA = 256 bytes output
AES_KEY_BYTES = 32    # AES-256
GCM_IV_BYTES  = 12    # standard for AES-GCM


def encrypt(payload: dict) -> str:
    """
    Encrypt a dict payload using hybrid RSA-OAEP + AES-256-GCM.
    Returns a base64 string suitable for wire transmission.
    """
    plaintext = json.dumps(payload, separators=(",", ":")).encode()

    # 1. Generate a fresh AES-256 key and 12-byte IV for this packet
    aes_key = os.urandom(AES_KEY_BYTES)
    iv = os.urandom(GCM_IV_BYTES)

    # 2. Encrypt payload with AES-256-GCM  (output = ciphertext + 16-byte tag)
    aesgcm = AESGCM(aes_key)
    aes_ct = aesgcm.encrypt(iv, plaintext, None)

    # 3. Encrypt AES key with RSA-OAEP (SHA-256)
    rsa_ct = ServerKeyHolder.get_public_key().encrypt(
        aes_key,
        asym_padding.OAEP(
            mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    # 4. Concatenate: [RSA blob][IV][AES-GCM ciphertext+tag]
    wire_bytes = rsa_ct + iv + aes_ct
    return base64.b64encode(wire_bytes).decode()


def decrypt(ciphertext_b64: str) -> dict:
    """
    Decrypt a hybrid ciphertext produced by encrypt().
    Raises ValueError / cryptography exceptions on tampered or invalid input.
    """
    wire_bytes = base64.b64decode(ciphertext_b64)

    # Split the wire format
    rsa_ct = wire_bytes[:RSA_KEY_BYTES]
    iv     = wire_bytes[RSA_KEY_BYTES: RSA_KEY_BYTES + GCM_IV_BYTES]
    aes_ct = wire_bytes[RSA_KEY_BYTES + GCM_IV_BYTES:]

    # 1. Unwrap the AES key with RSA-OAEP
    aes_key = ServerKeyHolder.get_private_key().decrypt(
        rsa_ct,
        asym_padding.OAEP(
            mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    # 2. Decrypt + verify GCM tag  (raises InvalidTag if tampered)
    aesgcm = AESGCM(aes_key)
    plaintext = aesgcm.decrypt(iv, aes_ct, None)

    return json.loads(plaintext.decode())


def ciphertext_hash(ciphertext_b64: str) -> str:
    """
    SHA-256 of the raw ciphertext bytes.
    Used as the idempotency key — computed BEFORE decryption so we don't
    spend RSA cycles on duplicates.
    """
    raw = base64.b64decode(ciphertext_b64)
    return hashlib.sha256(raw).hexdigest()
