from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Database URL format: postgresql://user:password@host:port/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://vmm_user:Umair%40825@localhost:5432/vmm_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
