#!/bin/bash
# setup_pizero2w.sh — D.E.A.L.E.R. provisioning for Raspberry Pi Zero 2W (Bookworm)
#
# Prerequisites — done BEFORE running this script:
#   1. Flashed Raspberry Pi OS Lite (32-bit, Bookworm) via Raspberry Pi Imager
#      with: hostname=dealer, SSH enabled, user=pi, home WiFi configured
#   2. SD card edited before first boot to enable USB gadget mode:
#        /boot/firmware/config.txt  → added:  dtoverlay=dwc2
#        /boot/firmware/cmdline.txt → added after rootwait:  modules-load=dwc2,g_ether
#   3. Connected Pi Zero 2W to Mac via USB DATA port (not PWR IN)
#   4. SSH'd in over USB gadget: ssh pi@dealer.local
#   5. Repo cloned: sudo git clone https://github.com/codedryfish/dealer.git /opt/dealer
#
# What this script does:
#   - Installs all packages while still on home WiFi (internet intact)
#   - Sets up Python venv, systemd service, mDNS
#   - Switches wlan0 from home WiFi → DEALER AP as the final step
#   - Reboots
#
# After reboot:
#   - SSH still works over USB cable: ssh pi@dealer.local  (USB gadget persists)
#   - wlan0 = DEALER AP (SSID=DEALER, 192.168.4.1) for ESP32 stations
#   - API at: http://192.168.4.1:8000
#
# Run as root: sudo bash /opt/dealer/pi/config/setup_pizero2w.sh

set -e

echo "=== D.E.A.L.E.R. Pi Zero 2W Setup ==="
echo "    (SSH over USB gadget — home WiFi used for internet during install)"
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
# Done LAST — preserves home WiFi (internet) for all steps above.
# SSH is over USB gadget (usb0), so this does NOT drop your connection.
echo "[7/7] Configuring DEALER WiFi AP on wlan0..."

nmcli con delete "preconfigured" 2>/dev/null || true
nmcli con delete "dealer-ap"     2>/dev/null || true

# SSID=DEALER, WPA2, static IP=192.168.4.1
# ipv4.method shared = NM handles DHCP for ESP32 clients
nmcli con add type wifi ifname wlan0 con-name dealer-ap ssid DEALER
nmcli con modify dealer-ap \
  802-11-wireless.mode ap \
  802-11-wireless.band bg \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.psk "dealermeplease" \
  ipv4.method shared \
  ipv4.address 192.168.4.1/24 \
  connection.autoconnect yes

echo ""
echo "=== Setup complete! Rebooting in 5 seconds... ==="
echo "    After reboot (USB cable stays connected):"
echo "    SSH:  ssh pi@dealer.local        (over USB gadget)"
echo "    AP:   SSID=DEALER / dealermeplease  (for ESP32s)"
echo "    API:  http://192.168.4.1:8000/api/health"
sleep 5
reboot
