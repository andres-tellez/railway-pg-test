# helper_extract_token.py

from src.db.db_session import get_session
from src.db.models.tokens import Token

session = get_session()
token_row = session.query(Token).filter_by(athlete_id=347085).first()
print("Access Token:", token_row.access_token)
session.close()
