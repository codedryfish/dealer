#!/bin/bash
# setup_pi.sh — One-shot Pi Zero 2 W provisioning for D.E.A.L.E.R.
# Run as root via SSH: sudo bash /tmp/setup_pi.sh
# This script is idempotent (safe to re-run).

set -e

echo "=== D.E.A.L.E.R. Pi Setup ==="

# ── 1. System update ────────────────────────────────────────────────────────
echo "[1/10] Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq

# ── 2. Install dependencies ─────────────────────────────────────────────────
echo "[2/10] Installing packages..."
apt-get install -y -qq \
  python3-pip python3-venv python3-dev \
  hostapd dnsmasq avahi-daemon \
  git curl

# ── 3. Configure WiFi AP ────────────────────────────────────────────────────
echo "[3/10] Configuring WiFi AP..."

# Static IP for wlan0
cat > /etc/dhcpcd.conf.dealer << 'EOF'
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF
grep -q "interface wlan0" /etc/dhcpcd.conf || cat /etc/dhcpcd.conf.dealer >> /etc/dhcpcd.conf

# hostapd config
cp /opt/dealer/pi/config/hostapd.conf /etc/hostapd/hostapd.conf
echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' > /etc/default/hostapd

# dnsmasq config
cp /opt/dealer/pi/config/dnsmasq.conf /etc/dnsmasq.conf

# ── 4. Enable services ──────────────────────────────────────────────────────
echo "[4/10] Enabling hostapd and dnsmasq..."
systemctl unmask hostapd
systemctl enable hostapd
systemctl enable dnsmasq

# ── 5. USB gadget mode (g_ether) ────────────────────────────────────────────
echo "[5/10] Configuring USB gadget mode..."
grep -q "dtoverlay=dwc2" /boot/config.txt || echo "dtoverlay=dwc2" >> /boot/config.txt
grep -q "modules-load=dwc2,g_ether" /boot/cmdline.txt || \
  sed -i 's/rootwait/rootwait modules-load=dwc2,g_ether/' /boot/cmdline.txt

# ── 6. Python venv and dependencies ─────────────────────────────────────────
echo "[6/10] Creating Python virtual environment..."
python3 -m venv /opt/dealer/venv
/opt/dealer/venv/bin/pip install --upgrade pip -q
/opt/dealer/venv/bin/pip install -r /opt/dealer/pi/requirements.txt -q

# ── 7. Set PYTHONPATH for the dealer package ─────────────────────────────────
echo "[7/10] Setting up Python path..."
echo "PYTHONPATH=/opt/dealer/pi" >> /opt/dealer/venv/bin/activate

# ── 8. Install systemd service ───────────────────────────────────────────────
echo "[8/10] Installing systemd service..."
cp /opt/dealer/pi/config/dealer.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable dealer

# ── 9. avahi mDNS (dealer.local) ────────────────────────────────────────────
echo "[9/10] Configuring mDNS..."
sed -i 's/#host-name=foo/host-name=dealer/' /etc/avahi/avahi-daemon.conf || true
systemctl enable avahi-daemon

# ── 10. Set permissions ──────────────────────────────────────────────────────
echo "[10/10] Setting permissions..."
chown -R pi:pi /opt/dealer

echo ""
echo "=== Setup complete! Rebooting in 5 seconds... ==="
echo "    After reboot: ssh pi@dealer.local"
echo "    API will be at: http://192.168.4.1:8000"
sleep 5
reboot
