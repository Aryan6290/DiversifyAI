import hashlib
import secrets
from typing import Optional
from db import SessionLocal, UserSession

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
    Creates a new active session token persistently in the database.
    """
    token = secrets.token_hex(32)
    db = SessionLocal()
    try:
        session = UserSession(token=token, user_id=user_id)
        db.add(session)
        db.commit()
    finally:
        db.close()
    return token

def get_user_id_by_session(token: str) -> Optional[int]:
    """
    Retrieves the user_id associated with a session token from the database.
    """
    db = SessionLocal()
    try:
        session = db.query(UserSession).filter(UserSession.token == token).first()
        return session.user_id if session else None
    finally:
        db.close()

def destroy_session(token: str) -> bool:
    """
    Deletes a session persistently from the database.
    """
    db = SessionLocal()
    try:
        session = db.query(UserSession).filter(UserSession.token == token).first()
        if session:
            db.delete(session)
            db.commit()
            return True
        return False
    finally:
        db.close()
