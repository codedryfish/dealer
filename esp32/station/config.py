"""
config.py — Station configuration.
Edit STATION_ID before flashing each ESP32.
"""

# Station identity: "A" for Agent Alpha, "B" for Agent Beta
STATION_ID = "A"

# WiFi credentials (Pi's access point)
WIFI_SSID = "DEALER"
WIFI_PASSWORD = "dealermeplease"

# Pi API base URL
API_BASE = "http://192.168.4.1:8000/api"

# Polling interval for action (seconds)
POLL_INTERVAL = 0.5

# Pin assignments (ESP32-S3)
# RFID (MFRC522) — SPI
PIN_RFID_SS  = 5   # Chip select
PIN_RFID_SCK = 18
PIN_RFID_MOSI = 23
PIN_RFID_MISO = 19
PIN_RFID_RST = 4

# OLED (SSD1306) — I2C
PIN_I2C_SDA = 21
PIN_I2C_SCL = 22
OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_ADDR = 0x3C

# LED ring (WS2812B)
PIN_LEDS = 16
LED_COUNT = 12

# Buzzer
PIN_BUZZER = 17

# Agent display name (shown on OLED)
AGENT_NAME = "Agent Alpha" if STATION_ID == "A" else "Agent Beta"
