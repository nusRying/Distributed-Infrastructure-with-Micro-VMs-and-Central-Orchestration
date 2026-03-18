from sqlalchemy.orm import Session
from models import Node, MicroVM
from sqlalchemy import func

class DecisionEngine:
    def __init__(self, db: Session):
        self.db = db

    def get_node_stats(self, node: Node):
        """
        Calculate heuristic score for a node.
        Higher score is better.
        """
        # Count active VMs on this node
        vm_count = self.db.query(func.count(MicroVM.id)).filter(
            MicroVM.node_id == node.id,
            MicroVM.status == 'running'
        ).scalar()

        # Base score starts at 100
        score = 100
        
        # Penalize for each running VM
        score -= (vm_count * 10)
        
        # Penalize based on reported load (if we had it, for now use a placeholder)
        # score -= (node.current_load * 5)
        
        # Bonus for high capacity (placeholder)
        # score += (node.total_ram_gb / 2)

        return score

    def select_best_node(self):
        """
        Find the best node for a new VM placement.
        """
        nodes = self.db.query(Node).all() # Should filter by 'active' status in real scenario
        if not nodes:
            return None
        
        best_node = None
        max_score = -float('inf')
        
        for node in nodes:
            score = self.get_node_stats(node)
            print(f"Node {node.hostname} (ID: {node.id}) - Score: {score}")
            if score > max_score:
                max_score = score
                best_node = node
                
        return best_node
