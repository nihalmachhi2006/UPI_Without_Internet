"""
ServerKeyHolder — generates and holds the RSA-2048 keypair for the lifetime of the process.
In production this would be backed by an HSM (AWS KMS / HashiCorp Vault).
"""

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import base64


class ServerKeyHolder:
    _private_key = None
    _public_key = None

    @classmethod
    def initialize(cls):
        cls._private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        cls._public_key = cls._private_key.public_key()

    @classmethod
    def get_private_key(cls):
        if cls._private_key is None:
            raise RuntimeError("ServerKeyHolder not initialized")
        return cls._private_key

    @classmethod
    def get_public_key(cls):
        if cls._public_key is None:
            raise RuntimeError("ServerKeyHolder not initialized")
        return cls._public_key

    @classmethod
    def get_public_key_b64(cls) -> str:
        """Return the public key as a base64-encoded DER blob (for the /api/server-key endpoint)."""
        der = cls.get_public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return base64.b64encode(der).decode()
