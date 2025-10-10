from sqlalchemy.exc import NoResultFound, IntegrityError
from sqlalchemy.dialects.postgresql import insert
from src.db.models.tokens import Token


def get_tokens_sa(session, athlete_id: int) -> dict | None:
    """
    Retrieves access, refresh, and expiration tokens for the given athlete.
    Returns None if not found.
    """
    try:
        token = session.query(Token).filter_by(athlete_id=athlete_id).one()
        return {
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "expires_at": token.expires_at,
        }
    except NoResultFound:
        print(f"No tokens found for athlete {athlete_id}", flush=True)
        return None


def insert_token_sa(
    session, athlete_id: int, access_token: str, refresh_token: str, expires_at: int
) -> None:
    """
    Inserts or updates a token record for the given athlete using upsert.
    Rolls back on error to prevent session poisoning.
    """
    stmt = (
        insert(Token)
        .values(
            athlete_id=athlete_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
        .on_conflict_do_update(
            index_elements=["athlete_id"],
            set_={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
            },
        )
    )

    try:
        session.execute(stmt)
        session.commit()
        print(f"Stored tokens for athlete {athlete_id}", flush=True)
    except IntegrityError as e:
        session.rollback()  # critical fix to avoid poisoned session
        print(
            f"Token insert/update failed for athlete {athlete_id}: {e}", flush=True
        )
        raise
    except Exception as e:
        session.rollback()
        print(
            f"Unexpected error inserting token for athlete {athlete_id}: {e}",
            flush=True,
        )
        raise


def delete_tokens_sa(session, athlete_id: int) -> int:
    """
    Deletes the token record for the given athlete.
    Returns the number of rows deleted.
    """
    try:
        result = session.query(Token).filter_by(athlete_id=athlete_id).delete()
        session.commit()
        print(f"Deleted {result} token(s) for athlete {athlete_id}", flush=True)
        return result
    except Exception as e:
        session.rollback()
        print(f"Failed to delete tokens for athlete {athlete_id}: {e}", flush=True)
        raise


# Alias for compatibility with code expecting `save_tokens_sa`
save_tokens_sa = insert_token_sa
