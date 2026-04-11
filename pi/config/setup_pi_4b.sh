#!/bin/bash
# setup_pi_4b.sh — D.E.A.L.E.R. provisioning for Raspberry Pi 4B (Bookworm)
#
# No ethernet required — runs over home WiFi, then switches wlan0 to DEALER AP on reboot.
#
# Differences from setup_pi.sh (Pi Zero 2W):
#   - Uses NetworkManager (nmcli) instead of hostapd/dhcpcd
#   - Skips USB gadget mode entirely
#   - All apt/pip installs happen BEFORE touching WiFi config (preserves internet)
#   - WiFi is switched to AP mode as the last step before reboot
#
# After reboot:
#   - wlan0 becomes the DEALER AP (SSID=DEALER, 192.168.4.1)
#   - SSH via: connect laptop to DEALER WiFi → ssh pi@192.168.4.1
#   - API at: http://192.168.4.1:8000
#
# Run as root: sudo bash /opt/dealer/pi/config/setup_pi_4b.sh

set -e

echo "=== D.E.A.L.E.R. Pi 4B Setup ==="
echo "    (Running over home WiFi — do not disconnect)"
echo ""

# ── 1. System update ────────────────────────────────────────────────────────
echo "[1/7] Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq

# ── 2. Install system dependencies ──────────────────────────────────────────
echo "[2/7] Installing packages..."
apt-get install -y -qq \
  python3-pip python3-venv python3-dev \
  avahi-daemon git curl

# ── 3. Python venv and pip dependencies ─────────────────────────────────────
echo "[3/7] Creating Python virtual environment and installing packages..."
python3 -m venv /opt/dealer/venv
/opt/dealer/venv/bin/pip install --upgrade pip -q
/opt/dealer/venv/bin/pip install -r /opt/dealer/pi/requirements.txt -q

# ── 4. Set PYTHONPATH ────────────────────────────────────────────────────────
echo "[4/7] Configuring Python path..."
grep -q "PYTHONPATH" /opt/dealer/venv/bin/activate || \
  echo "export PYTHONPATH=/opt/dealer/pi" >> /opt/dealer/venv/bin/activate

# Inject PYTHONPATH into the systemd service if not already there
grep -q "PYTHONPATH" /opt/dealer/pi/config/dealer.service || \
  sed -i '/\[Service\]/a Environment=PYTHONPATH=/opt/dealer/pi' \
    /opt/dealer/pi/config/dealer.service

# ── 5. Install systemd service + mDNS ───────────────────────────────────────
echo "[5/7] Installing systemd service and mDNS..."
cp /opt/dealer/pi/config/dealer.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable dealer

sed -i 's/#host-name=foo/host-name=dealer/' /etc/avahi/avahi-daemon.conf || true
systemctl enable avahi-daemon

# ── 6. Set permissions ───────────────────────────────────────────────────────
echo "[6/7] Setting permissions..."
chown -R pi:pi /opt/dealer

# ── 7. Switch wlan0 to DEALER AP ────────────────────────────────────────────
# Done LAST so all internet-dependent steps above complete successfully.
# SSH will drop after this step — that's expected. Pi reboots immediately.
echo "[7/7] Configuring DEALER WiFi AP (this will drop your SSH connection)..."

# Remove existing wlan0 client connections
nmcli con delete "preconfigured" 2>/dev/null || true
nmcli con delete "dealer-ap"     2>/dev/null || true

# Create AP: SSID=DEALER, WPA2, IP=192.168.4.1
# ipv4.method shared = NM runs its own DHCP for connecting clients (ESP32s)
nmcli con add type wifi ifname wlan0 con-name dealer-ap ssid DEALER
nmcli con modify dealer-ap \
  802-11-wireless.mode ap \
  802-11-wireless.band bg \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.proto rsn \
  wifi-sec.pairwise ccmp \
  wifi-sec.group ccmp \
  wifi-sec.psk "dealermeplease" \
  ipv4.method shared \
  ipv4.address 192.168.4.1/24 \
  connection.autoconnect yes
# proto rsn / pairwise+group ccmp = WPA2-only (AES).
# Without this, nmcli may default to WPA (TKIP) which ESP-IDF 5.x rejects
# with status 211 (WIFI_REASON_NO_AP_FOUND_IN_RSSI_THRESHOLD).

echo ""
echo "=== Setup complete! Rebooting in 5 seconds... ==="
echo "    After reboot:"
echo "    1. Connect your laptop to WiFi: DEALER / dealermeplease"
echo "    2. SSH:  ssh pi@192.168.4.1"
echo "    3. API:  http://192.168.4.1:8000/api/health"
sleep 5
reboot
