import requests
import time
import json

BASE_URL = "http://localhost:8001"

def test_infrastructure():
    print("--- 1. Registering Node ---")
    node_data = {
        "hostname": "test-node",
        "ip_address": "127.0.0.1",
        "capacity_ram_mb": 1024,
        "capacity_vcpus": 2
    }
    resp = requests.post(f"{BASE_URL}/node/register", json=node_data)
    if resp.status_code != 200:
        print(f"Failed to register node: {resp.text}")
        return
    node = resp.json()
    node_id = node['id']
    print(f"Successfully registered node. ID: {node_id}")

    print("\n--- 2. Submitting Task ---")
    task_data = {
        "code": "echo 'Hello from the agent!'",
        "target": "vm"
    }
    resp = requests.post(f"{BASE_URL}/task", json=task_data)
    if resp.status_code != 200:
        print(f"Failed to submit task: {resp.text}")
        return
    task_info = resp.json()
    task_id = task_info['id']
    print(f"Successfully submitted task. ID: {task_id}")

    print("\n--- 3. Polling for Task ---")
    resp = requests.get(f"{BASE_URL}/task/next", params={"node_id": node_id})
    if resp.status_code != 200 or resp.json() is None:
        print(f"Failed to poll for task or no task available: {resp.text}")
        return
    task = resp.json()
    print(f"Polling task {task['id']} (type: {task['type']})")

    print("\n--- 4. Sending Result ---")
    result_data = {"result": "Successfully echoed!"}
    resp = requests.post(f"{BASE_URL}/task/{task['id']}/result", json=result_data)
    if resp.status_code != 200:
        print(f"Failed to send result: {resp.text}")
        return
    print("Successfully reported task completion.")

    print("\n--- 5. Verifying Task Final Status ---")
    resp = requests.get(f"{BASE_URL}/task/{task['id']}")
    if resp.status_code != 200:
        print(f"Failed to verify task status: {resp.text}")
        return
    final_status = resp.json()
    print(f"Final Task Status: {final_status['status']}")
    print(f"Final Task Result: {final_status['result']}")

if __name__ == "__main__":
    test_infrastructure()
