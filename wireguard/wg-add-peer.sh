#!/bin/bash
set -e

if [ "$#" -ne 2 ]; then
    echo "Usage: ./wg-add-peer.sh <node_id> <ip_last_octet>"
    echo "Example: ./wg-add-peer.sh vm-101 101"
    exit 1
fi

NODE_ID=$1
OCTET=$2
WG_DIR="$(pwd)"
SERVER_PUB=$(cat "$WG_DIR/server_public.key")

# Peer keys
PEER_PRIV_FILE="$WG_DIR/peers/${NODE_ID}_private.key"
PEER_PUB_FILE="$WG_DIR/peers/${NODE_ID}_public.key"
PEER_CONF="$WG_DIR/peers/${NODE_ID}.conf"

mkdir -p "$WG_DIR/peers"

if [ ! -f "$PEER_PRIV_FILE" ]; then
    wg genkey | tee "$PEER_PRIV_FILE" | wg pubkey > "$PEER_PUB_FILE"
fi

PEER_PRIV=$(cat "$PEER_PRIV_FILE")
PEER_PUB=$(cat "$PEER_PUB_FILE")
PEER_IP="10.0.0.$OCTET"

echo "Adding peer $NODE_ID to wg0..."
sudo wg set wg0 peer "$PEER_PUB" allowed-ips "$PEER_IP/32"

echo "Creating peer config: $PEER_CONF"
# Assuming control server is reachable via the WSL host IP or typical ethernet interface.
# For WSL, the host IP might be dynamically assigned. We'll use 10.0.0.1 for VM-to-Host communication
# if the WireGuard interface is correctly bound. Wait, if the VM is running inside WSL, it can reach the WSL IP.
# We will use the eth0 IP of WSL as the endpoint.

ENDPOINT_IP=$(ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

cat <<EOF > "$PEER_CONF"
[Interface]
PrivateKey = $PEER_PRIV
Address = $PEER_IP/24

[Peer]
PublicKey = $SERVER_PUB
AllowedIPs = 10.0.0.0/24
Endpoint = $ENDPOINT_IP:51820
PersistentKeepalive = 25
EOF

echo "Peer added. Config generated at $PEER_CONF"
