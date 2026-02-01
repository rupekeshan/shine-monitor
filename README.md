# Shine Monitor Integration for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/rupekeshan/shine-monitor.svg)](https://github.com/rupekeshan/shine-monitor/releases)
[![License](https://img.shields.io/github/license/rupekeshan/shine-monitor.svg)](LICENSE)

A Home Assistant custom integration for monitoring solar power plants via the [Shine Monitor](https://www.shinemonitor.com/) cloud API.

## Features

- **Real-time Monitoring**: Current power output, daily/monthly/yearly/total energy production
- **Environmental Impact**: CO₂ reduction, SO₂ reduction, coal savings
- **Financial Tracking**: Daily and total profit with configurable currency
- **Device Status**: Online/offline status for inverters and dataloggers
- **Alarm Monitoring**: Active alarm count and problem indicators
- **Historical Data Import**: Import past energy data into Home Assistant's long-term statistics
- **Energy Dashboard Ready**: Sensors are compatible with Home Assistant's Energy Dashboard

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots menu → "Custom repositories"
4. Add `https://github.com/rupekeshan/shine-monitor` with category "Integration"
5. Click "Install"
6. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub](https://github.com/rupekeshan/shine-monitor/releases)
2. Copy the `custom_components/shine_monitor` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Shine Monitor"
4. Enter your credentials:
   - **Username**: Your Shine Monitor account email
   - **Password**: Your Shine Monitor account password
   - **Company Key**: Your company key (found in the Shine Monitor app settings)
5. Select your solar plant from the list

### Finding Your Company Key

The company key can be found in the Shine Monitor mobile app:
1. Open the Shine Monitor app
2. Go to Settings/Profile
3. Look for "Company Key" or "API Key"

## Sensors

### Plant Sensors

| Sensor | Description | Unit |
|--------|-------------|------|
| Current Power | Real-time power output | kW |
| Daily Energy | Energy produced today | kWh |
| Monthly Energy | Energy produced this month | kWh |
| Yearly Energy | Energy produced this year | kWh |
| Total Energy | Lifetime energy production | kWh |
| Installed Capacity | Total installed capacity | kW |
| Active Alarms | Number of active alarms | count |

### Environmental Sensors

| Sensor | Description | Unit |
|--------|-------------|------|
| Daily/Total Profit | Financial savings | Configurable |
| Daily/Total Coal Saving | Equivalent coal not burned | kg |
| Daily/Total CO₂ Reduction | Carbon dioxide avoided | kg |
| Daily/Total SO₂ Reduction | Sulfur dioxide avoided | kg |

### Binary Sensors

| Sensor | Description |
|--------|-------------|
| Has Active Alarms | ON when there are active plant alarms |
| Device Online | Connectivity status for each inverter/datalogger |

## Options

After setup, you can configure these options:

| Option | Description | Default |
|--------|-------------|---------|
| Update Interval | Data refresh rate (1-60 minutes) | 5 minutes |
| Currency | Currency symbol for profit display | ₹ |
| Enable Devices | Show per-device sensors | Yes |

## Services

### `shine_monitor.import_history`

Import historical energy data into Home Assistant's long-term statistics.

| Parameter | Description | Required |
|-----------|-------------|----------|
| start_date | Date to start importing from (YYYY-MM-DD) | No |

Example:
```yaml
service: shine_monitor.import_history
data:
  start_date: "2023-01-01"
```

## Energy Dashboard

To add your solar production to the Energy Dashboard:

1. Go to **Settings** → **Dashboards** → **Energy**
2. Under "Solar Panels", click **Add Solar Production**
3. Select the "Daily Energy" sensor from this integration

## Troubleshooting

### Authentication Failed
- Verify your username, password, and company key are correct
- Ensure your Shine Monitor account has API access enabled

### No Plants Found
- Check that your account has at least one plant registered
- Verify the plant is visible in the Shine Monitor app

### Data Not Updating
- Check your internet connection
- Verify the Shine Monitor cloud service is operational
- Try increasing the update interval in options

## Requirements

- Home Assistant 2024.1.0 or newer
- Active Shine Monitor account with registered solar plant(s)
- Valid company key for API access

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests on [GitHub](https://github.com/rupekeshan/shine-monitor).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This integration is not officially affiliated with or endorsed by Shine Monitor. Use at your own risk.
