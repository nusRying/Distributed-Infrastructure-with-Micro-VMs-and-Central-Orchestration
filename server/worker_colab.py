import time
import requests
import subprocess
import os
import json
import logging
import threading

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] COLAB_WORKER: %(message)s")

SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:8000")
COLAB_NOTEBOOK_URL = os.environ.get("COLAB_NOTEBOOK_URL", "https://colab.research.google.com/drive/1example")
COLAB_RUNNER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "colab", "colab_runner.py"))

def register_node():
    for _ in range(10):
        try:
            resp = requests.post(f"{SERVER_URL}/node/register", json={
                "hostname": "colab-worker",
                "ip_address": "127.0.0.1",
                "capacity_ram_mb": 8192,
                "capacity_vcpus": 4
            }, timeout=5)
            if resp.status_code == 200:
                node = resp.json()
                logging.info(f"Registered colab worker successfully. Node ID: {node['id']}")
                return node['id']
        except Exception as e:
            logging.warning(f"Registration failed, retrying... {e}")
            time.sleep(3)
    raise Exception("Could not register with server")

def execute_task(task):
    task_id = task['id']
    payload = task['payload']
    
    try:
        data = json.loads(payload)
        code = data.get('code', '')
    except Exception as e:
        code = ""
        
    logging.info(f"Executing task {task_id}")
    
    # Run the playwright colab_runner
    try:
        proc = subprocess.run(
            ["python", COLAB_RUNNER_PATH, "--notebook", COLAB_NOTEBOOK_URL, "--code", code],
            capture_output=True,
            text=True,
            timeout=300 # 5 minute timeout
        )
        
        result = proc.stdout
        if proc.stderr:
            result += "\n[STDERR]\n" + proc.stderr
            
    except Exception as e:
        result = f"Error running colab runner: {str(e)}"
        
    logging.info(f"Task {task_id} completed, sending result.")
    
    # Post result
    try:
        requests.post(f"{SERVER_URL}/task/{task_id}/result", json={
            "result": result
        })
    except Exception as e:
        logging.error(f"Failed to post result for {task_id}: {e}")

def ping_loop(node_id):
    while True:
        time.sleep(15)
        try:
            requests.post(f"{SERVER_URL}/node/{node_id}/ping")
        except Exception:
            pass

def main():
    node_id = register_node()
    
    t = threading.Thread(target=ping_loop, args=(node_id,), daemon=True)
    t.start()
    
    logging.info("Starting task poll loop...")
    while True:
        try:
            resp = requests.get(f"{SERVER_URL}/task/next", params={"node_id": node_id})
            if resp.status_code == 200:
                task = resp.json()
                if task:
                    execute_task(task)
                else:
                    time.sleep(2)
            else:
                time.sleep(2)
        except Exception as e:
            logging.error(f"Poll error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
