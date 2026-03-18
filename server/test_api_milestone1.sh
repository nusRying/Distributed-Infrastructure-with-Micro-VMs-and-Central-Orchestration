#!/bin/bash
echo "--- Health Check ---"
curl -s http://127.0.0.1:8000/health
echo -e "\n\n--- Node Register ---"
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"hostname":"worker-02", "ip_address":"192.168.1.101", "capacity_ram_mb":32768, "capacity_vcpus":16}' \
  http://127.0.0.1:8000/node/register
echo -e "\n\n--- List Nodes ---"
curl -s http://127.0.0.1:8000/nodes
echo -e "\n\n--- Create VM Task ---"
VM_ID="test-vm-$RANDOM"
JOB_RESP=$(curl -s -X POST -H 'Content-Type: application/json' \
  -d "{\"vm_id\":\"$VM_ID\", \"vcpus\":1, \"memory_mb\":512}" \
  http://127.0.0.1:8000/task/vm-create)
echo $JOB_RESP
JOB_ID=$(echo $JOB_RESP | grep -oP '(?<="job_id":")[^"]*')
if [ ! -z "$JOB_ID" ]; then
  echo -e "\n--- Job Status ($JOB_ID) ---"
  sleep 2
  curl -s http://127.0.0.1:8000/job/$JOB_ID
fi
echo -e "\n"
