"""Constants for the SAJ Solar & Battery Monitor integration."""

DOMAIN = "saj_monitor"
CONF_APP_ID = "app_id"
CONF_APP_SECRET = "app_secret"

# Devices
CONF_DEVICES = "devices"
CONF_DEVICE_NAME = "name"
CONF_DEVICE_SN = "sn"
CONF_DEVICE_PLANT_ID = "plant_id"
CONF_DEVICE_TYPE = "type"

# Device types
DEVICE_TYPE_SOLAR = "solar" 
DEVICE_TYPE_BATTERY = "battery"
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes

# Icons
SOLAR_ICON = "mdi:solar-power"
BATTERY_ICON = "mdi:battery"
POWER_ICON = "mdi:flash"
ENERGY_ICON = "mdi:lightning-bolt"
GRID_ICON = "mdi:transmission-tower"
TEMPERATURE_ICON = "mdi:thermometer"
MONEY_ICON = "mdi:currency-usd"
CO2_ICON = "mdi:molecule-co2"
EFFICIENCY_ICON = "mdi:chart-bell-curve"
ONLINE_ICON = "mdi:lan-connect"
OFFLINE_ICON = "mdi:lan-disconnect"

# API URLs
BASE_URL = "https://intl-developer.saj-electric.com"
TOKEN_URL = "/prod-api/open/api/access_token"
DEVICE_INFO_URL = "/prod-api/open/api/device/batInfo"
PLANT_STATS_URL = "/prod-api/open/api/plant/getPlantStatisticsData"
HISTORY_DATA_URL = "/prod-api/open/api/device/historyDataCommon"
LOAD_MONITORING_URL = "/prod-api/open/api/device/secData"
REALTIME_DATA_URL = "/prod-api/open/api/device/realtimeDataCommon"

# Error messages
ERROR_AUTH = "Authentication failed. Please check your credentials."
ERROR_COMM = "Communication error. Please check your internet connection."
ERROR_UNKNOWN = "Unknown error occurred."
