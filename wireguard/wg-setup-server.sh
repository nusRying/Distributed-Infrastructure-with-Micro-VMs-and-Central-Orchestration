#!/bin/bash
set -e

WG_DIR="$(pwd)"
SERVER_CONF="$WG_DIR/wg0.conf"
SERVER_PRIV="$WG_DIR/server_private.key"
SERVER_PUB="$WG_DIR/server_public.key"

if [ ! -f "$SERVER_PRIV" ]; then
    echo "Generating Server Keys..."
    wg genkey | tee "$SERVER_PRIV" | wg pubkey > "$SERVER_PUB"
fi

PRIV_KEY=$(cat "$SERVER_PRIV")

echo "Creating wg0.conf..."
cat <<EOF > "$SERVER_CONF"
[Interface]
Address = 10.0.0.1/24
ListenPort = 51820
PrivateKey = $PRIV_KEY
SaveConfig = false
EOF

echo "Starting WireGuard interface wg0..."
# Attempt to bring it up using wg-quick (requires sudo/root usually)
# If running as non-root in WSL without systemd, this might need sudo.
sudo wg-quick down wg0 2>/dev/null || true
sudo wg-quick up "$SERVER_CONF"

echo "WireGuard Server running. IP: 10.0.0.1"
sudo wg show
