import logging
from sqlalchemy.exc import NoResultFound, IntegrityError
from sqlalchemy.dialects.postgresql import insert
from src.db.models.tokens import Token

logger = logging.getLogger(__name__)


def get_tokens_sa(session, athlete_id: int) -> dict | None:
    """
    Retrieves access, refresh, and expiration tokens for the given athlete.
    Returns None if not found.

    Note: Tokens are automatically decrypted when accessed via Token model properties.
    """
    try:
        token = session.query(Token).filter_by(athlete_id=athlete_id).one()

        # Check if token is revoked
        if token.is_revoked():
            logger.warning(f"Token for athlete {athlete_id} has been revoked")
            return None

        # Tokens are automatically decrypted via @hybrid_property
        return {
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "expires_at": token.expires_at,
        }
    except NoResultFound:
        logger.debug(f"No tokens found for athlete {athlete_id}")
        return None


def insert_token_sa(
    session, athlete_id: int, access_token: str, refresh_token: str, expires_at: int
) -> None:
    """
    Inserts or updates a token record for the given athlete using upsert.
    Rolls back on error to prevent session poisoning.

    Note: Tokens are automatically encrypted when set via Token model properties.
    """
    # Create Token instance (encryption happens via @hybrid_property setters)
    token = Token()
    token.athlete_id = athlete_id
    token.access_token = access_token  # Automatically encrypted
    token.refresh_token = refresh_token  # Automatically encrypted
    token.expires_at = expires_at
    token.revoked_at = None  # Clear revocation if updating

    stmt = (
        insert(Token)
        .values(
            athlete_id=token.athlete_id,
            access_token=token._encrypted_access_token,  # Use encrypted value
            refresh_token=token._encrypted_refresh_token,  # Use encrypted value
            expires_at=token.expires_at,
            revoked_at=None,  # Clear revocation on update
        )
        .on_conflict_do_update(
            index_elements=["athlete_id"],
            set_={
                "access_token": token._encrypted_access_token,
                "refresh_token": token._encrypted_refresh_token,
                "expires_at": token.expires_at,
                "revoked_at": None,  # Clear revocation on update
            },
        )
    )

    try:
        session.execute(stmt)
        session.commit()
        logger.info(f"Stored tokens for athlete {athlete_id}")
    except IntegrityError as e:
        session.rollback()  # critical fix to avoid poisoned session
        logger.error(f"Token insert/update failed for athlete {athlete_id}: {e}")
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Unexpected error inserting token for athlete {athlete_id}: {e}")
        raise


def delete_tokens_sa(session, athlete_id: int) -> int:
    """
    Deletes the token record for the given athlete.
    Returns the number of rows deleted.
    """
    try:
        result = session.query(Token).filter_by(athlete_id=athlete_id).delete()
        session.commit()
        logger.info(f"Deleted {result} token(s) for athlete {athlete_id}")
        return result
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to delete tokens for athlete {athlete_id}: {e}")
        raise


# Alias for compatibility with code expecting `save_tokens_sa`
save_tokens_sa = insert_token_sa
