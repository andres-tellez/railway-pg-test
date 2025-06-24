# scripts/debug_token.py

import os
from dotenv import load_dotenv
from src.db.db_session import get_session
from src.db.dao.token_dao import get_tokens_sa

load_dotenv(".env.prod")
session = get_session()
token = get_tokens_sa(session, 347085)
print("🔐 Token from DB:", token)
session.close()
