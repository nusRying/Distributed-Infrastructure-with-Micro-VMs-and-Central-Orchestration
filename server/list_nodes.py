from database import SessionLocal
from models import Node

db = SessionLocal()
nodes = db.query(Node).all()
print(f"Total nodes in database: {len(nodes)}")
for n in nodes:
    print(f"ID: {n.id}, Hostname: {n.hostname}, Status: {n.status}")
db.close()
