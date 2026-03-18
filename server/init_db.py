from database import engine, SessionLocal
from models import Base, Node

# Create tables
Base.metadata.create_all(bind=engine)

def init_nodes():
    db = SessionLocal()
    # Check if node already exists
    if db.query(Node).filter(Node.hostname == "node-01").first():
        print("Node node-01 already exists")
    else:
        new_node = Node(
            hostname="node-01",
            ip_address="192.168.1.100",
            status="online",  # Start it as online for testing
            capacity_ram_mb=16384,
            capacity_vcpus=8
        )
        db.add(new_node)
        db.commit()
        print("Initialized node-01")
    db.close()

if __name__ == "__main__":
    init_nodes()
