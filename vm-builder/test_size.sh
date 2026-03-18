#!/bin/bash
# test_size.sh
# Verifies that Alpine + wireguard-tools-wg + UPX AGENT fits in a 15MB rootfs.

set -e

# Use the password provided by the user
PASS="Umair@825"

TIMESTAMP=$(date +%s)
ROOTFS="/tmp/rootfs_${TIMESTAMP}.ext4"
MNTDIR="/tmp/mnt_${TIMESTAMP}"
mkdir -p "$MNTDIR"

echo "==> Creating 15 MB ext4 image (No journal, 0% reserve, explicit inode count)..."
dd if=/dev/zero of="$ROOTFS" bs=1M count=15 status=none
# -N 1024: 1024 inodes total (plenty for Alpine + WG + Agent)
mkfs.ext4 -F -m 0 -O ^has_journal -N 1024 "$ROOTFS" 2>/dev/null

echo "==> Mounting image..."
echo "$PASS" | sudo -S mount -o loop "$ROOTFS" "$MNTDIR"

echo "==> Extracting Alpine minirootfs..."
ALPINE_PATH="/mnt/c/Users/umair/Videos/Freelance/Aoi Kei/Project 2/vm-builder/alpine.tar.gz"
if [ ! -f "$ALPINE_PATH" ]; then
    echo "Alpine tarball not found at $ALPINE_PATH, downloading..."
    curl -sL "https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/x86_64/alpine-minirootfs-3.19.1-x86_64.tar.gz" -o /tmp/alpine.tar.gz
    ALPINE_PATH="/tmp/alpine.tar.gz"
fi
echo "$PASS" | sudo -S tar xf "$ALPINE_PATH" -C "$MNTDIR"

echo "==> Bind-mounting for chroot..."
echo "$PASS" | sudo -S mount --bind /proc "$MNTDIR/proc"
echo "$PASS" | sudo -S mount --bind /dev  "$MNTDIR/dev"
echo "$PASS" | sudo -S mount --bind /sys  "$MNTDIR/sys"
echo "$PASS" | sudo -S cp /etc/resolv.conf "$MNTDIR/etc/resolv.conf"

echo "==> Installing wireguard-tools-wg (minimal) + cleanup..."
echo "$PASS" | sudo -S chroot "$MNTDIR" /bin/sh -c "apk add --no-cache wireguard-tools-wg && rm -rf /var/cache/apk/* /usr/share/man /usr/share/doc /usr/share/help /usr/lib/engines-3 /usr/lib/ossl-modules" 2>&1 | tail -n 5

echo "==> Preparing agent..."
AGENT_PATH="/mnt/c/Users/umair/Videos/Freelance/Aoi Kei/Project 2/agent/agent"
UPX_BIN="/tmp/upx-4.2.4-amd64_linux/upx"
STRIPPED_AGENT="/tmp/stripped_agent"
PACKED_AGENT="/tmp/upx_agent"

strip -s "$AGENT_PATH" -o "$STRIPPED_AGENT"
rm -f "$PACKED_AGENT"

if command -v upx >/dev/null 2>&1; then
    upx -9 -q -o "$PACKED_AGENT" "$STRIPPED_AGENT"
elif [ -f "$UPX_BIN" ]; then
    "$UPX_BIN" -9 -q -o "$PACKED_AGENT" "$STRIPPED_AGENT"
else
    echo "WARN: upx not found, using stripped binary only"
    cp "$STRIPPED_AGENT" "$PACKED_AGENT"
fi

echo "==> Injecting agent..."
echo "$PASS" | sudo -S mkdir -p "$MNTDIR/usr/local/bin"
echo "$PASS" | sudo -S cp /tmp/upx_agent "$MNTDIR/usr/local/bin/agent"
echo "$PASS" | sudo -S chmod +x "$MNTDIR/usr/local/bin/agent"

echo "==> Unmounting..."
echo "$PASS" | sudo -S umount "$MNTDIR/proc" || true
echo "$PASS" | sudo -S umount "$MNTDIR/dev"  || true
echo "$PASS" | sudo -S umount "$MNTDIR/sys"  || true
echo "$PASS" | sudo -S umount "$MNTDIR"

TOTAL=$(echo "$PASS" | sudo -S dumpe2fs -h "$ROOTFS" 2>/dev/null | grep "Block count:" | awk '{print $3}')
FREE=$(echo "$PASS" | sudo -S dumpe2fs  -h "$ROOTFS" 2>/dev/null | grep "Free blocks:" | awk '{print $3}')
BLKSZ=$(echo "$PASS" | sudo -S dumpe2fs -h "$ROOTFS" 2>/dev/null | grep "Block size:" | awk '{print $3}')
USED_BYTES=$(( (TOTAL - FREE) * BLKSZ ))
USED_MB=$(echo "scale=2; $USED_BYTES / 1024 / 1024" | bc)

echo "==> Space used inside image: ~${USED_MB} MB / 15 MB"
if [ $(echo "$USED_MB <= 15" | bc) -eq 1 ]; then
    echo "==> PASSED: Alpine + minimal WG + UPX Agent fit within 15 MB"
else
    echo "==> FAILED: image content exceeds 15 MB"
fi

rm -rf "$MNTDIR" "$ROOTFS" /tmp/stripped_agent /tmp/upx_agent
