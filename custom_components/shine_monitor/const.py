"""Constants for the Shine Monitor integration."""
from datetime import timedelta

DOMAIN = "shine_monitor"

# API Configuration
API_BASE_URL = "https://api.shinemonitor.com/public/"
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=5)
REAUTH_INTERVAL = timedelta(hours=24)

# Configuration keys
CONF_COMPANY_KEY = "company_key"
CONF_PLANT_ID = "plant_id"
CONF_PLANT_NAME = "plant_name"
CONF_TOKEN = "token"
CONF_SECRET = "secret"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_CURRENCY = "currency"
CONF_ENABLE_DEVICES = "enable_devices"

# Default options
DEFAULT_CURRENCY = "₹"
DEFAULT_ENABLE_DEVICES = True

# Currency options
CURRENCY_OPTIONS = {
    "₹": "Indian Rupee (₹)",
    "$": "US Dollar ($)",
    "€": "Euro (€)",
    "£": "British Pound (£)",
    "¥": "Japanese Yen (¥)",
    "A$": "Australian Dollar (A$)",
    "C$": "Canadian Dollar (C$)",
}

# API Actions - Authentication
ACTION_AUTH = "auth"
ACTION_UPDATE_TOKEN = "updateToken"

# API Actions - Plant Data
ACTION_QUERY_PLANTS = "queryPlants"
ACTION_QUERY_PLANT_INFO = "queryPlantInfo"
ACTION_QUERY_PLANT_DEVICE_VIEW = "queryPlantDeviceView"
ACTION_QUERY_PLANT_DEVICE_STATUS = "queryPlantDeviceStatus"
ACTION_QUERY_PLANT_ENERGY_DAY = "queryPlantEnergyDay"
ACTION_QUERY_PLANT_ENERGY_MONTH = "queryPlantEnergyMonth"
ACTION_QUERY_PLANT_ENERGY_YEAR = "queryPlantEnergyYear"
ACTION_QUERY_PLANT_ENERGY_TOTAL = "queryPlantEnergyTotal"
ACTION_QUERY_PLANT_ENERGY_MONTH_PER_DAY = "queryPlantEnergyMonthPerDay"
ACTION_QUERY_PLANT_ENERGY_YEAR_PER_MONTH = "queryPlantEnergyYearPerMonth"
ACTION_QUERY_PLANT_ENERGY_TOTAL_PER_YEAR = "queryPlantEnergyTotalPerYear"
ACTION_QUERY_PLANT_ACTIVE_OUTPUT_POWER_CURRENT = "queryPlantsActiveOuputPowerCurrent"
ACTION_QUERY_PLANT_ACTIVE_OUTPUT_POWER_ONE_DAY = "queryPlantActiveOuputPowerOneDay"
ACTION_QUERY_PLANT_WARNING_COUNT = "queryPlantWarningCount"
ACTION_QUERY_PLANT_WARNING_DEVICE_COUNT = "queryPlantWarningDeviceCount"
ACTION_QUERY_PLANT_ENV_MONITOR = "queryPlantEnvMonitor"
ACTION_QUERY_PLANTS_PROFIT_ONE_DAY = "queryPlantsProfitOneDay"
ACTION_QUERY_PLANTS_PROFIT = "queryPlantsProfit"
ACTION_QUERY_PLANT_RUNNING_NORMAL_TIME = "queryPlantRunningNormalTime"
ACTION_QUERY_PLANTS_NOMINAL_POWER = "queryPlantsNominalPower"

# API Actions - Datalogger/Collector
ACTION_QUERY_COLLECTORS = "queryCollectors"
ACTION_QUERY_COLLECTOR_INFO = "queryCollectorInfo"
ACTION_QUERY_COLLECTOR_STATUS = "queryCollectorStatus"
ACTION_QUERY_COLLECTOR_DEVICES = "queryCollectorDevices"
ACTION_QUERY_COLLECTOR_DEVICES_STATUS = "queryCollectorDevicesStatus"

# API Actions - Device Data
ACTION_QUERY_DEVICES = "queryDevices"
ACTION_QUERY_DEVICE_INFO = "queryDeviceInfo"
ACTION_QUERY_DEVICE_LAST_DATA = "queryDeviceLastData"
ACTION_QUERY_DEVICE_STATUS = "queryDeviceStatus"
ACTION_QUERY_DEVICE_DATA_ONE_DAY = "queryDeviceDataOneDay"
ACTION_QUERY_DEVICE_WARNING = "queryDeviceWarning"
ACTION_QUERY_DEVICE_WARNING_COUNT = "queryDeviceWarningCount"
ACTION_QUERY_DEVICE_ENERGY_DAY = "queryDeviceEnergyDay"
ACTION_QUERY_DEVICE_ENERGY_MONTH = "queryDeviceEnergyMonth"
ACTION_QUERY_DEVICE_ENERGY_YEAR = "queryDeviceEnergyYear"
ACTION_QUERY_DEVICE_ENERGY_TOTAL = "queryDeviceEnergyTotal"
ACTION_QUERY_DEVICE_ENERGY_MONTH_PER_DAY = "queryDeviceEnergyMonthPerDay"
ACTION_QUERY_DEVICE_ENERGY_YEAR_PER_MONTH = "queryDeviceEnergyYearPerMonth"
ACTION_QUERY_DEVICE_ACTIVE_OUTPUT_POWER_CURRENT = "queryDeviceActiveOuputPowerCurrent"
ACTION_QUERY_DEVICE_ACTIVE_OUTPUT_POWER_ONE_DAY = "queryDeviceActiveOuputPowerOneDay"
ACTION_QUERY_DEVICE_RATE_ACTIVE_OUTPUT_POWER = "queryDeviceRateActiveOutputPower"

# Device Types
DEVICE_TYPE_INVERTER = "inverter"
DEVICE_TYPE_DATALOGGER = "datalogger"
DEVICE_TYPE_BATTERY = "battery"
DEVICE_TYPE_METER = "meter"

# Device Status
DEVICE_STATUS_ONLINE = "online"
DEVICE_STATUS_OFFLINE = "offline"
DEVICE_STATUS_ALARM = "alarm"

# Sensor Keys for coordinator data
DATA_CURRENT_POWER = "current_power"
DATA_DAILY_ENERGY = "daily_energy"
DATA_MONTHLY_ENERGY = "monthly_energy"
DATA_YEARLY_ENERGY = "yearly_energy"
DATA_TOTAL_ENERGY = "total_energy"
DATA_PROFIT = "profit"
DATA_COAL = "coal"
DATA_CO2 = "co2"
DATA_SO2 = "so2"
DATA_LAST_UPDATED = "last_updated"
DATA_PLANT_INFO = "plant_info"
DATA_DEVICES = "devices"
DATA_DATALOGGERS = "dataloggers"
DATA_WARNING_COUNT = "warning_count"
DATA_INSTALLED_CAPACITY = "installed_capacity"
DATA_INVERTER_FAULT_COUNT = "inverter_fault_count"
DATA_GRID_FAULT_COUNT = "grid_fault_count"
DATA_INVERTER_ALARMS = "inverter_alarms"
DATA_GRID_ALARMS = "grid_alarms"
DATA_LATEST_ALARM = "latest_alarm"
DATA_LATEST_INVERTER_FAULT = "latest_inverter_fault"

# Grid-related alarm codes (power cuts, grid issues - can be ignored)
# These are normal events in areas with unreliable power
GRID_FAULT_CODES = {
    "0x00000009",  # No utility fault (grid down / power cut)
    "0x0000000A",  # Grid voltage over fault
    "0x0000000B",  # Grid voltage under fault  
    "0x0000000C",  # Grid frequency over fault
    "0x0000000D",  # Grid frequency under fault
    "0x00000011",  # No grid connection
    "0x00000012",  # Grid lost
}

# Service names
SERVICE_IMPORT_HISTORY = "import_history"
SERVICE_IMPORT_POWER_HISTORY = "import_power_history"
SERVICE_REFRESH_DATA = "refresh_data"

# Attributes
ATTR_PLANT_ID = "plant_id"
ATTR_DEVICE_ID = "device_id"
ATTR_START_DATE = "start_date"
ATTR_END_DATE = "end_date"

# Icons
ICON_SOLAR_POWER = "mdi:solar-power"
ICON_SOLAR_PANEL = "mdi:solar-panel"
ICON_ENERGY = "mdi:lightning-bolt"
ICON_PROFIT = "mdi:currency-usd"
ICON_COAL = "mdi:molecule-co2"
ICON_CO2 = "mdi:molecule-co2"
ICON_SO2 = "mdi:molecule"
ICON_INVERTER = "mdi:current-ac"
ICON_DATALOGGER = "mdi:access-point"
ICON_WARNING = "mdi:alert"
ICON_TEMPERATURE = "mdi:thermometer"
ICON_VOLTAGE = "mdi:flash"
ICON_CURRENT = "mdi:current-dc"
ICON_FREQUENCY = "mdi:sine-wave"
ICON_CAPACITY = "mdi:gauge"
ICON_RUNTIME = "mdi:clock-outline"
