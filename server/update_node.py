from database import SessionLocal
from models import Node

db = SessionLocal()
node = db.query(Node).first()
if node:
    node.status = 'online'
    db.commit()
    print(f"Node {node.hostname} updated to online")
else:
    print("No nodes found in database")
db.close()
