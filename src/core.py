# src/db_core.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

def get_engine(db_url):
    return create_engine(db_url, future=True)

def get_session(engine):
    return sessionmaker(bind=engine, future=True)()
