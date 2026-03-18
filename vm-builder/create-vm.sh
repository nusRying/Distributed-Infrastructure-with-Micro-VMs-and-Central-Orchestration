#!/bin/bash
# vm-builder/create-vm.sh
# Creates a minimal rootfs for Firecracker, injects the Go agent, and prepares it for launch.

set -e

NODE_ID=$1
OCTET=$2
if [ -z "$NODE_ID" ] || [ -z "$OCTET" ]; then
    echo "Usage: ./create-vm.sh <node_id> <ip_last_octet>"
    exit 1
fi

echo "==> Building micro-VM for Node: $NODE_ID"

# 1. Generate Wireguard Peer Config
if [ -z "$SKIP_WG" ]; then
    echo "==> Generating WireGuard config..."
    cd ../wireguard
    ./wg-add-peer.sh $NODE_ID $OCTET
    cd ../vm-builder
else
    echo "==> Skipping WireGuard config (SKIP_WG set)..."
    mkdir -p ../wireguard/peers
    touch "../wireguard/peers/${NODE_ID}.conf"
fi

WG_CONF="../wireguard/peers/${NODE_ID}.conf"
if [ ! -f "$WG_CONF" ]; then
    echo "Error: WireGuard config generation failed"
    exit 1
fi

# 2. Prepare RootFS
ROOTFS="rootfs_${NODE_ID}.ext4"
echo "==> Creating root filesystem ($ROOTFS)..."
# Optimized ext4 for 15MB limit:
# -m 0: No reserved blocks
# -O ^has_journal: No journal to save space
# -N 1024: Fewer inodes (approx 1 per 15KB) to reduce overhead
dd if=/dev/zero of=$ROOTFS bs=1M count=15 status=none
mkfs.ext4 -F -m 0 -O ^has_journal -N 1024 $ROOTFS

# Create a temporary mount point
MOUNT_DIR=$(mktemp -d)
sudo mount $ROOTFS $MOUNT_DIR

# Export alpine to rootfs
echo "==> Extracting Alpine Linux Mini RootFS..."
if [ ! -f "alpine.tar.gz" ]; then
    curl -sL "https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/x86_64/alpine-minirootfs-3.19.1-x86_64.tar.gz" -o alpine.tar.gz
fi
sudo tar xf alpine.tar.gz -C $MOUNT_DIR

# Pre-install minimal wireguard-tools at BUILD TIME via chroot
# Mount helper filesystems so apk can reach the network.
echo "==> Pre-installing wireguard-tools-wg (build-time, via chroot)..."
sudo mount --bind /proc $MOUNT_DIR/proc
sudo mount --bind /dev  $MOUNT_DIR/dev
sudo mount --bind /sys  $MOUNT_DIR/sys
sudo cp /etc/resolv.conf $MOUNT_DIR/etc/resolv.conf

# Use wireguard-tools and clean apk cache immediately
sudo chroot $MOUNT_DIR /bin/sh -c "apk add --no-cache wireguard-tools && rm -rf /var/cache/apk/* /lib/apk /etc/apk /usr/share/apk"

# Aggressive rootfs cleanup before agent injection
echo "==> Aggressive cleanup of unused files..."
sudo chroot $MOUNT_DIR /bin/sh -c "rm -rf /usr/share/man /usr/share/doc /usr/share/help /usr/lib/engines-3 /usr/lib/ossl-modules /usr/share/zoneinfo /usr/share/perl5"

echo "==> Space after cleanup:"
sudo df -h $MOUNT_DIR

# Unmount helper filesystems before injecting files
sudo umount $MOUNT_DIR/proc || true
sudo umount $MOUNT_DIR/dev  || true
sudo umount $MOUNT_DIR/sys  || true

# 3. Inject Agent & Config
echo "==> Injecting Agent and WG configs..."
# We pack the agent with UPX if available to save ~3MB
AGENT_SRC="../agent/agent"
if [ -f "$AGENT_SRC" ]; then
    echo "==> Packing agent with UPX..."
    STRIPPED_AGENT="/tmp/agent_stripped_${NODE_ID}"
    PACKED_AGENT="/tmp/agent_packed_${NODE_ID}"
    strip -s "$AGENT_SRC" -o "$STRIPPED_AGENT"
    rm -f "$PACKED_AGENT"
    
    # Try to use upx if installed, otherwise use stripped version
    if command -v upx >/dev/null 2>&1; then
        upx -9 -q -o "$PACKED_AGENT" "$STRIPPED_AGENT"
    elif [ -f "/tmp/upx-4.2.4-amd64_linux/upx" ]; then
        /tmp/upx-4.2.4-amd64_linux/upx -9 -q -o "$PACKED_AGENT" "$STRIPPED_AGENT"
    else
        echo "WARN: upx not found, using stripped binary only"
        cp "$STRIPPED_AGENT" "$PACKED_AGENT"
    fi
    
    sudo cp "$PACKED_AGENT" $MOUNT_DIR/usr/local/bin/agent
    sudo chmod +x $MOUNT_DIR/usr/local/bin/agent
    rm -f "$STRIPPED_AGENT" "$PACKED_AGENT"
else
    echo "WARN: Go agent not found at $AGENT_SRC. Please build it!"
fi

sudo mkdir -p $MOUNT_DIR/etc/wireguard
sudo cp $WG_CONF $MOUNT_DIR/etc/wireguard/wg0.conf

# 4. Setup init script (Alpine uses OpenRC but sysvinit style inittab works)
# For the micro-VM, we hook standard mountings and the agent launch.
cat <<EOF | sudo tee $MOUNT_DIR/etc/inittab >/dev/null
::sysinit:/bin/sh -c 'mount -t proc proc /proc; mount -t sysfs sys /sys'
::sysinit:/bin/sh -c 'ip link set lo up'
::sysinit:/bin/sh -c 'wg-quick up wg0 || true'
::respawn:/usr/local/bin/agent
EOF

sudo umount $MOUNT_DIR
rm -rf $MOUNT_DIR

FINAL_SIZE=$(stat -c%s "$ROOTFS" 2>/dev/null || stat -f%z "$ROOTFS")
FINAL_MB=$(( FINAL_SIZE / 1024 / 1024 ))
echo "==> RootFS created: $ROOTFS (${FINAL_MB} MB)"
if [ "$FINAL_MB" -le 15 ]; then
    echo "==> ✓ Size check PASSED (≤ 15 MB)"
else
    echo "==> ✗ WARNING: Image is ${FINAL_MB} MB — exceeds 15 MB limit!"
fi
echo "==> Use ./launch.sh $NODE_ID to boot the VM."
