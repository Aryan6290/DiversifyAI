import hashlib
import secrets
import os
from typing import Dict, Optional

# process-wide token session storage
ACTIVE_SESSIONS: Dict[str, int] = {}

def generate_salt() -> str:
    """
    Generates a secure, random 32-character salt.
    """
    return secrets.token_hex(16)

def hash_password(password: str, salt: str) -> str:
    """
    Hashes a password with SHA-256 and the provided salt.
    """
    hasher = hashlib.sha256()
    hasher.update((password + salt).encode('utf-8'))
    return hasher.hexdigest()

def verify_password(password: str, salt: str, password_hash: str) -> bool:
    """
    Verifies a password against the stored salt and hash.
    """
    return hash_password(password, salt) == password_hash

def create_session(user_id: int) -> str:
    """
    Creates a new active session token and records it in-memory.
    """
    token = secrets.token_hex(32)
    ACTIVE_SESSIONS[token] = user_id
    return token

def get_user_id_by_session(token: str) -> Optional[int]:
    """
    Retrieves the user_id associated with a session token.
    """
    return ACTIVE_SESSIONS.get(token)

def destroy_session(token: str) -> bool:
    """
    Deletes an active session.
    """
    if token in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[token]
        return True
    return False
