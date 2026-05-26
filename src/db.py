import os
import json
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from dotenv import load_dotenv

load_dotenv()

# Fetch DB connection string. Default is PostgreSQL, fallback to SQLite.
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgresql+pg8000://postgres:postgres@localhost:5432/diversify_ai"

# SQLAlchemy setup
try:
    if DATABASE_URL.startswith("postgresql"):
        # Attempt to connect to check availability
        temp_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        with temp_engine.connect() as conn:
            pass
        engine = temp_engine
        print("🔌 Connected to PostgreSQL database successfully.")
    else:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
except Exception as e:
    print(f"⚠️ PostgreSQL connection failed ({e}). Falling back to local SQLite database.")
    sqlite_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diversify_ai.db")
    DATABASE_URL = f"sqlite:///{sqlite_path}"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    """
    Main user account for authentication and secure session-based analytics.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(512), nullable=False)
    salt = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    subscription = relationship("UserSubscription", back_populates="user", uselist=False, cascade="all, delete-orphan")

class UserSession(Base):
    """
    Stores session tokens persistently in the database so that login persists
    even across server restarts, worker recyclings, and sleeps.
    """
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class UserSubscription(Base):
    """
    Tracks email subscriptions for daily agent monitoring and reports.
    """
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    model = Column(String(255), nullable=True)
    api_key = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="subscription")
    portfolio = relationship("UserPortfolio", back_populates="subscription", uselist=False, cascade="all, delete-orphan")
    reports = relationship("DailyReport", back_populates="subscription", cascade="all, delete-orphan")

class UserPortfolio(Base):
    """
    Persists holdings for a given email subscriber so the background
    agent can perform monitoring asynchronously.
    """
    __tablename__ = "user_portfolios"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("user_subscriptions.id", ondelete="CASCADE"), unique=True)
    holdings_json = Column(JSON, nullable=False) # List of holding dicts
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    subscription = relationship("UserSubscription", back_populates="portfolio")

class DailyReport(Base):
    """
    Logs generated daily advisor reports for user reference.
    """
    __tablename__ = "daily_reports"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("user_subscriptions.id", ondelete="CASCADE"))
    report_json = Column(JSON, nullable=False) # Serialized report dict from Gemini
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    subscription = relationship("UserSubscription", back_populates="reports")

def init_db():
    """
    Initializes database tables and safely updates schemas.
    """
    Base.metadata.create_all(bind=engine)
    
    # Safely migrate existing tables to include model and api_key columns
    db = SessionLocal()
    try:
        from sqlalchemy import text
        if engine.dialect.name == "sqlite":
            try:
                db.execute(text("ALTER TABLE user_subscriptions ADD COLUMN model VARCHAR(255)"))
                db.commit()
            except Exception:
                db.rollback()
            try:
                db.execute(text("ALTER TABLE user_subscriptions ADD COLUMN api_key VARCHAR(255)"))
                db.commit()
            except Exception:
                db.rollback()
        else:
            # PostgreSQL
            try:
                db.execute(text("ALTER TABLE user_subscriptions ADD COLUMN IF NOT EXISTS model VARCHAR(255)"))
                db.commit()
            except Exception:
                db.rollback()
            try:
                db.execute(text("ALTER TABLE user_subscriptions ADD COLUMN IF NOT EXISTS api_key VARCHAR(255)"))
                db.commit()
            except Exception:
                db.rollback()
    finally:
        db.close()

def get_db():
    """
    Dependency helper to fetch a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
