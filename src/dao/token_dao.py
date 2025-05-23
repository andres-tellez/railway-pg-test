from sqlalchemy.exc import NoResultFound, IntegrityError
from src.models.tokens import Token

def get_tokens_sa(session, athlete_id):
    try:
        token = session.query(Token).filter_by(athlete_id=athlete_id).one()
        return {
            "access_token": token.access_token,
            "refresh_token": token.refresh_token
        }
    except NoResultFound:
        return None

def save_tokens_sa(session, athlete_id, access_token, refresh_token):
    try:
        token = session.query(Token).filter_by(athlete_id=athlete_id).one_or_none()
        if token:
            token.access_token = access_token
            token.refresh_token = refresh_token
        else:
            token = Token(
                athlete_id=athlete_id,
                access_token=access_token,
                refresh_token=refresh_token,
            )
            session.add(token)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise RuntimeError(f"Failed to save tokens via SQLAlchemy: {e}")
