# src/utils/auth_helpers.py
"""
Deprecated shim file. Do NOT duplicate JWT logic here.
Delegates to src.utils.auth0_jwt to ensure single source of truth.
"""

from src.utils.auth0_jwt import requires_auth

# ✅ Re-export only
__all__ = ["requires_auth"]
