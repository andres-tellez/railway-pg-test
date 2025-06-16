from sqlalchemy.exc import NoResultFound
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
        return None


def insert_token_sa(session, athlete_id: int, access_token: str, refresh_token: str, expires_at: int) -> None:
    """
    Inserts or updates a token record for the given athlete using upsert.
    """
    stmt = insert(Token).values(
        athlete_id=athlete_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at
    ).on_conflict_do_update(
        index_elements=["athlete_id"],
        set_={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at
        }
    )

    session.execute(stmt)
    session.commit()


def delete_tokens_sa(session, athlete_id: int) -> int:
    """
    Deletes the token record for the given athlete.
    Returns the number of rows deleted.
    """
    result = session.query(Token).filter_by(athlete_id=athlete_id).delete()
    session.commit()
    return result
