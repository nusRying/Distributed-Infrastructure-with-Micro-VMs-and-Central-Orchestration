#!/bin/bash
# vm-builder/launch.sh
# Launches a Firecracker micro-VM using a pre-built rootfs and WireGuard config.

set -e

NODE_ID=$1
if [ -z "$NODE_ID" ]; then
    echo "Usage: ./launch.sh <node_id>"
    exit 1
fi

ROOTFS="rootfs_${NODE_ID}.ext4"
if [ ! -f "$ROOTFS" ]; then
    echo "Error: Root filesystem $ROOTFS not found!"
    echo "Run ./create-vm.sh $NODE_ID first."
    exit 1
fi

# We expect a vmlinux kernel to be present. You can download one if missing.
KERNEL="vmlinux"
if [ ! -f "$KERNEL" ]; then
    echo "==> Downloading default Firecracker kernel..."
    curl -sL "https://s3.amazonaws.com/spec.ccfc.min/img/quickstart_guide/x86_64/kernels/vmlinux.bin" -o $KERNEL
fi

API_SOCKET="/tmp/firecracker_${NODE_ID}.socket"
rm -f $API_SOCKET

echo "==> Starting Firecracker for Node: $NODE_ID..."

# Use absolute path to the firecracker binary in the parent dir
FC_BIN_PATH="$(pwd)/../firecracker/firecracker"
"$FC_BIN_PATH" --api-sock "$API_SOCKET" > "firecracker_${NODE_ID}.log" 2>&1 &
FC_PID=$!

sleep 1

echo "==> Configuring VM Kernel..."
curl -s -X PUT --unix-socket $API_SOCKET \
  http://localhost/boot-source \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d "{
        \"kernel_image_path\": \"$(pwd)/$KERNEL\",
        \"boot_args\": \"console=ttyS0 reboot=k panic=1 pci=off init=/sbin/init SERVER_URL=http://172.16.0.1:8000 NODE_ID=${NODE_ID}\"
      }" > /dev/null

echo "==> Configuring VM RootFS..."
curl -s -X PUT --unix-socket $API_SOCKET \
  http://localhost/drives/rootfs \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d "{
        \"drive_id\": \"rootfs\",
        \"path_on_host\": \"$(pwd)/$ROOTFS\",
        \"is_root_device\": true,
        \"is_read_only\": false
      }" > /dev/null

# Setup host-side networking
  BR_NAME="fc-br0"
  TAP_NAME="tap_$NODE_ID"
  
  # Create bridge if not exists
  if ! ip link show "$BR_NAME" > /dev/null 2>&1; then
    echo "==> Creating bridge $BR_NAME..."
    sudo ip link add name "$BR_NAME" type bridge
    sudo ip addr add 172.16.0.1/24 dev "$BR_NAME"
    sudo ip link set dev "$BR_NAME" up
  fi

  # Create TAP device if not exists
  if ! ip link show "$TAP_NAME" > /dev/null 2>&1; then
    echo "==> Creating TAP device $TAP_NAME..."
    sudo ip tuntap add dev "$TAP_NAME" mode tap
  fi
  
  sudo ip link set dev "$TAP_NAME" master "$BR_NAME"
  sudo ip link set dev "$TAP_NAME" up

  # Configure VM Network Interface
  echo "==> Configuring Network Interface ($TAP_NAME)..."
  curl -s -X PUT --unix-socket "$API_SOCKET" \
    "http://localhost/network-interfaces/eth0" \
    -H "Content-Type: application/json" \
    -d "{
        \"iface_id\": \"eth0\",
        \"guest_mac\": \"06:00:00:00:00:65\",
        \"host_dev_name\": \"$TAP_NAME\"
      }" > /dev/null

echo "==> Starting VM..."
curl -s -X PUT --unix-socket $API_SOCKET \
  http://localhost/actions \
  -H  'Accept: application/json' \
  -H  'Content-Type: application/json' \
  -d "{
        \"action_type\": \"InstanceStart\"
      }" > /dev/null

echo "=================================================="
echo "VM $NODE_ID is running (PID: $FC_PID)"
echo "API Socket: $API_SOCKET"
echo "To terminate: kill $FC_PID && rm -f $API_SOCKET"
echo "=================================================="
