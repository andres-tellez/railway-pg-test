import uuid
from datetime import datetime
from typing import Mapping, Any, Optional, Dict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.db.db_session import get_session
from src.db.models.user_identity import UserIdentity
from src.db.models.user_auth_providers import UserAuthProvider


# ----------------------
# Basic Getters
# ----------------------


def get_by_user_id(user_id: str) -> Optional[UserIdentity]:
    db = get_session()
    return db.query(UserIdentity).filter(UserIdentity.user_id == user_id).first()


def get_by_email(email: str) -> Optional[UserIdentity]:
    db = get_session()
    return db.query(UserIdentity).filter(UserIdentity.email == email).first()


# ----------------------
# Upsert Identity
# ----------------------


import logging

logger = logging.getLogger(__name__)


def upsert_identity(payload: Mapping[str, Any]) -> uuid.UUID:
    """
    Insert or update a user_identity record.
    - If email exists, reuse the DB's existing user_id.
    - Prevents duplicate UUIDs when reusing an email.
    - Returns the canonical user_id from DB.
    """
    db = get_session()

    stmt = insert(UserIdentity).values(**payload)

    if payload.get("email"):
        # Conflict on email → do NOT overwrite user_id
        stmt = stmt.on_conflict_do_update(
            index_elements=["email"],
            set_={
                "email_verified": stmt.excluded.email_verified,
                "name": stmt.excluded.name,
                "picture": stmt.excluded.picture,
                "updated_at": stmt.excluded.updated_at,
            },
        )
    else:
        # Conflict on user_id (for no-email case)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id"],
            set_={
                "email": stmt.excluded.email,
                "email_verified": stmt.excluded.email_verified,
                "name": stmt.excluded.name,
                "picture": stmt.excluded.picture,
                "updated_at": stmt.excluded.updated_at,
            },
        )

    # Always return canonical user_id (not payload's)
    stmt = stmt.returning(UserIdentity.user_id)

    result = db.execute(stmt).scalar()
    db.commit()
    db.close()
    return result


# ----------------------
# Resolve from Auth Provider
# ----------------------

from src.utils.normalize_claims import normalize_claims

_UUID5_NAMESPACE = uuid.UUID("2b81d1b2-3d6a-4a0a-b8c3-2c6a2fd2a8ad")


def resolve_user_id_from_auth_provider(
    sub: str,
    userinfo: Optional[Dict[str, Any]] = None,
    create_if_missing: bool = False,
) -> Optional[uuid.UUID]:
    """
    Resolution order:
      1) If provider mapping (sub) exists → return its user_id
      2) Else if create_if_missing==False → return None
      3) Else → upsert identity (reusing by email if available)
      4) Always return canonical user_id from DB
    """
    if not sub:
        return None

    # Be defensive: some identity providers or misconfigured clients may
    # provide a sub without a 'provider|' prefix. In that case, fall back
    # to a sane default so we can still create/link an identity.
    try:
        provider_name, provider_user_id = sub.split("|", 1)
    except ValueError:
        logger.warning(
            "resolve_user_id_from_auth_provider: unexpected sub format '%s' "
            "(expected 'provider|id'). Falling back to provider_name='unknown'.",
            sub,
        )
        provider_name, provider_user_id = "unknown", sub
    claims = normalize_claims(userinfo or {})

    email = claims.get("email")
    name = claims.get("name")
    email_verified = claims.get("email_verified")
    picture = claims.get("picture")

    print(
        "resolve_user_id_from_auth_provider: opening DB session (primary)", flush=True
    )
    db = get_session()
    print("resolve_user_id_from_auth_provider: DB session (primary) opened", flush=True)
    try:
        # 1) Existing provider mapping?
        print(
            f"resolve_user_id_from_auth_provider: querying existing mapping for provider={provider_name} user_id={provider_user_id}",
            flush=True,
        )
        existing_user_id = db.execute(
            select(UserAuthProvider.user_id).where(
                UserAuthProvider.provider_name == provider_name,
                UserAuthProvider.provider_user_id == provider_user_id,
            )
        ).scalar()
        print(
            f"resolve_user_id_from_auth_provider: mapping query returned {existing_user_id}",
            flush=True,
        )
        if existing_user_id:
            return existing_user_id

        # 2) Read-only mode
        if not create_if_missing:
            return None

        # 3) Decide user_id (reuse by email if present)
        if email:
            reuse_user_id = db.execute(
                select(UserIdentity.user_id).where(UserIdentity.email == email)
            ).scalar()
            user_id = reuse_user_id if reuse_user_id else uuid.uuid4()
        else:
            # Deterministic UUID fallback if no email
            user_id = uuid.uuid5(_UUID5_NAMESPACE, sub)

        # 4) Upsert identity (ensures canonical UUID is returned)
        payload = {
            "user_id": user_id,
            "email": email,
            "email_verified": email_verified,
            "name": name,
            "picture": picture,
            "updated_at": datetime.utcnow(),
        }
        canonical_user_id = upsert_identity(payload)

        # 5) Link provider → canonical_user_id
        db.execute(
            insert(UserAuthProvider)
            .values(
                user_id=canonical_user_id,
                full_provider_id=sub,
                provider_name=provider_name,
                provider_user_id=provider_user_id,
            )
            .on_conflict_do_nothing()
        )
        db.commit()
    finally:
        db.close()

    # 6) Re-fetch with a fresh session to be 100% consistent
    print("resolve_user_id_from_auth_provider: opening DB session (verify)", flush=True)
    db2 = get_session()
    print("resolve_user_id_from_auth_provider: DB session (verify) opened", flush=True)
    try:
        print(
            f"resolve_user_id_from_auth_provider: verifying mapping for provider={provider_name} user_id={provider_user_id}",
            flush=True,
        )
        final_user_id = db2.execute(
            select(UserAuthProvider.user_id).where(
                UserAuthProvider.provider_name == provider_name,
                UserAuthProvider.provider_user_id == provider_user_id,
            )
        ).scalar()
        print(
            f"resolve_user_id_from_auth_provider: verification query returned {final_user_id}",
            flush=True,
        )
        return final_user_id
    finally:
        print(
            "resolve_user_id_from_auth_provider: closing DB session (verify)",
            flush=True,
        )
        db2.close()
