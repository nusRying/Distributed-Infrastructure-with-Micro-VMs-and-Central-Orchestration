import sys
import os

# Add the server directory to sys.path to import from it
server_dir = os.path.join(os.getcwd(), 'server')
sys.path.append(server_dir)

from database import SessionLocal
from models import Node

db = SessionLocal()
node = db.query(Node).filter(Node.hostname == 'test-node').first()
if node:
    node.status = 'online'
    db.commit()
    print(f"Node {node.hostname} updated to online.")
else:
    print("Node not found.")
db.close()
