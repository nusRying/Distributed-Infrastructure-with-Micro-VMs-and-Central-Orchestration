import sys
import os

from sqlalchemy import text
from database import SessionLocal

def upgrade():
    db = SessionLocal()
    try:
        db.execute(text('ALTER TABLE tasks ADD COLUMN IF NOT EXISTS node_id INTEGER REFERENCES nodes(id)'))
        db.execute(text('ALTER TABLE tasks ADD COLUMN IF NOT EXISTS checkpoint VARCHAR'))
        db.commit()
        print("Database schema updated successfully!")
    except Exception as e:
        print(f"Error updating schema: {e}")
    finally:
        db.close()

if __name__ == '__main__':
    upgrade()
