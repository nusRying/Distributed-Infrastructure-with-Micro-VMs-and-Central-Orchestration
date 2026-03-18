import sqlite3
import os

db_path = os.path.join('server', 'database.db')
conn = sqlite3.connect(db_path)
conn.execute("UPDATE nodes SET status='online' WHERE hostname='test-node'")
conn.commit()
conn.close()
print("Node status updated to online.")
