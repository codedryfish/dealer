#!/bin/bash
# setup_pi_4b.sh — D.E.A.L.E.R. provisioning for Raspberry Pi 4B (Bookworm)
#
# Differences from setup_pi.sh:
#   - Uses NetworkManager for WiFi AP (not hostapd/dhcpcd)
#   - Skips USB gadget mode (use ethernet for SSH instead)
#   - Targets /boot/firmware/ for Bookworm boot partition
#
# Prerequisites:
#   - Pi 4B running Raspberry Pi OS Lite 64-bit (Bookworm)
#   - Ethernet cable connected to router (for internet + SSH during setup)
#   - Code cloned to /opt/dealer
#
# Run as root: sudo bash /opt/dealer/pi/config/setup_pi_4b.sh

set -e

echo "=== D.E.A.L.E.R. Pi 4B Setup ==="

# ── 1. System update ────────────────────────────────────────────────────────
echo "[1/7] Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq

# ── 2. Install dependencies ─────────────────────────────────────────────────
echo "[2/7] Installing packages..."
apt-get install -y -qq \
  python3-pip python3-venv python3-dev \
  avahi-daemon git curl

# NetworkManager is pre-installed on Bookworm; verify it's running
systemctl enable NetworkManager
systemctl start NetworkManager

# ── 3. Configure WiFi AP via NetworkManager ──────────────────────────────────
echo "[3/7] Configuring WiFi AP (wlan0 → SSID: DEALER)..."

# Remove any existing wlan0 connections to avoid conflicts
nmcli con delete "dealer-ap" 2>/dev/null || true
nmcli con delete "preconfigured" 2>/dev/null || true

# Create AP: SSID=DEALER, WPA2 password=dealermeplease, static IP=192.168.4.1
# ipv4.method shared = NetworkManager handles DHCP for connecting ESP32s
nmcli con add type wifi ifname wlan0 con-name dealer-ap ssid DEALER
nmcli con modify dealer-ap \
  802-11-wireless.mode ap \
  802-11-wireless.band bg \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.psk "dealermeplease" \
  ipv4.method shared \
  ipv4.address 192.168.4.1/24 \
  connection.autoconnect yes

nmcli con up dealer-ap || echo "[warn] AP bring-up deferred to reboot (ok)"

# ── 4. Python venv and dependencies ─────────────────────────────────────────
echo "[4/7] Creating Python virtual environment..."
python3 -m venv /opt/dealer/venv
/opt/dealer/venv/bin/pip install --upgrade pip -q
/opt/dealer/venv/bin/pip install -r /opt/dealer/pi/requirements.txt -q

# ── 5. Set PYTHONPATH ────────────────────────────────────────────────────────
echo "[5/7] Setting up Python path..."
grep -q "PYTHONPATH" /opt/dealer/venv/bin/activate || \
  echo "export PYTHONPATH=/opt/dealer/pi" >> /opt/dealer/venv/bin/activate

# Also set it in the systemd service environment
grep -q "PYTHONPATH" /opt/dealer/pi/config/dealer.service || \
  sed -i '/Environment=DEALER_MODE/i Environment=PYTHONPATH=/opt/dealer/pi' \
    /opt/dealer/pi/config/dealer.service

# ── 6. Install systemd service ───────────────────────────────────────────────
echo "[6/7] Installing systemd service..."
cp /opt/dealer/pi/config/dealer.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable dealer

# ── 7. avahi mDNS (dealer.local) + permissions ──────────────────────────────
echo "[7/7] Configuring mDNS and permissions..."
sed -i 's/#host-name=foo/host-name=dealer/' /etc/avahi/avahi-daemon.conf || true
systemctl enable avahi-daemon
chown -R pi:pi /opt/dealer

echo ""
echo "=== Setup complete! Rebooting in 5 seconds... ==="
echo "    After reboot, SSH via ethernet:  ssh pi@dealer.local"
echo "    DEALER WiFi AP will be live:     SSID=DEALER / pass=dealermeplease"
echo "    Game API:                        http://192.168.4.1:8000"
echo "    Web UI:                          http://192.168.4.1:8000/index.html"
sleep 5
reboot
