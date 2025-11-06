from sqlalchemy import Column, BigInteger, String, DateTime
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime
from src.db.db_session import Base  # ✅ use shared Base


class Token(Base):
    __tablename__ = "tokens"

    athlete_id = Column(BigInteger, primary_key=True)
    _encrypted_access_token = Column(
        "access_token", String, nullable=False
    )  # Encrypted at rest
    _encrypted_refresh_token = Column(
        "refresh_token", String, nullable=False
    )  # Encrypted at rest
    expires_at = Column(BigInteger, nullable=False)
    revoked_at = Column(DateTime, nullable=True)  # Token revocation timestamp

    @hybrid_property
    def access_token(self):
        """Decrypt access token when accessed."""
        from src.utils.token_encryption import decrypt_token

        return decrypt_token(self._encrypted_access_token)

    @access_token.setter
    def access_token(self, value):
        """Encrypt access token when set."""
        from src.utils.token_encryption import encrypt_token

        self._encrypted_access_token = encrypt_token(value)

    @hybrid_property
    def refresh_token(self):
        """Decrypt refresh token when accessed."""
        from src.utils.token_encryption import decrypt_token

        return decrypt_token(self._encrypted_refresh_token)

    @refresh_token.setter
    def refresh_token(self, value):
        """Encrypt refresh token when set."""
        from src.utils.token_encryption import encrypt_token

        self._encrypted_refresh_token = encrypt_token(value)

    def is_revoked(self) -> bool:
        """Check if token has been revoked."""
        return self.revoked_at is not None

    def revoke(self):
        """Revoke the token immediately."""
        self.revoked_at = datetime.utcnow()
