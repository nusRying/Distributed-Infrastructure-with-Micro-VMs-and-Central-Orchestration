import time
from database import SessionLocal
from models import MicroVM, Node
from decision_engine import DecisionEngine

def process_vm_creation(vm_id: str, node_id: int = None):
    """
    Background task to handle VM creation.
    If node_id is None, use DecisionEngine to select one.
    """
    print(f"Starting creation process for VM: {vm_id}")
    db = SessionLocal()
    try:
        # If node_id not provided, find the best one
        if node_id is None:
            engine = DecisionEngine(db)
            best_node = engine.select_best_node()
            if not best_node:
                print(f"Error: No available nodes for VM {vm_id}")
                return False
            node_id = best_node.id
            print(f"Decision Engine selected Node ID: {node_id}")

        # 1. Update status to 'provisioning'
        vm = MicroVM(vm_id=vm_id, node_id=node_id, status='provisioning')
        db.add(vm)
        db.commit()
        
        # 2. Simulate provisioning steps
        time.sleep(2)  # Network setup
        print(f"[{vm_id}] Network configured...")
        
        time.sleep(3)  # Firecracker boot
        print(f"[{vm_id}] Firecracker instance started on Node {node_id}")
        
        # 3. Finalize status
        vm.status = 'running'
        db.commit()
        print(f"VM {vm_id} is successfully running on Node {node_id}")
        return True
    except Exception as e:
        print(f"Error processing VM {vm_id}: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def run_agent_command(node_id: int, command: str):
    """
    Mock task for running agent command
    """
    print(f"Running command '{command}' on node {node_id}...")
    time.sleep(2)
    return {"status": "executed", "output": "Mock output"}
