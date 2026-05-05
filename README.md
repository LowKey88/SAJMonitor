# SAJ Monitor - Home Assistant Integration

A Home Assistant custom component for monitoring SAJ solar inverters and battery systems. This integration fetches data from the SAJ cloud API and presents it as sensors within Home Assistant.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=lowkey88&repository=SAJMonitor&category=integration)

## Features

- Monitor SAJ solar inverters and battery systems
- View real-time power generation, grid status, and battery information
- Track daily and total energy production
- Monitor home load power and self-consumption
- Use eSolar SEC plant load-monitoring data as the preferred source for home load when available
- Track SEC data freshness, self-consumed solar energy, self-consumption rate, and solar offset rate
- Estimate daily TNB Domestic ToU + NEM cost from SEC import/export energy using a bill-derived blended model
- Support for both solar inverters and battery systems
- Automatic detection of nighttime mode for solar inverters
- Environmental impact statistics (CO2 reduction, equivalent trees)

<!-- Add screenshots here once available -->
<!-- 
## Screenshots

![Integration](https://raw.githubusercontent.com/lowkey88/SAJMonitor/main/images/integration.png)
![Sensors](https://raw.githubusercontent.com/lowkey88/SAJMonitor/main/images/sensors.png)
-->

## Prerequisites

Before installing this integration, you need to obtain SAJ Developer API credentials and device information:

### 1. Getting API Credentials

1. **Register as a Developer on the SAJ Elekeeper Platform:**
   - Log in to the [Elekeeper web portal](https://intl-developer.saj-electric.com)
   - Find the developers function on the top of the portal
   - Choose "Autonomous Account"
   - Complete the developer registration form
   - Wait for SAJ to process your application

2. **Obtain Your API Credentials:**
   - After approval, navigate to the developer console
   - Go to "App Configuration" in the settings menu
   - You'll receive:
     - App ID
     - App Secret
   - Keep these credentials handy for the integration setup

3. **Authorize Resources:**
   - Set up which plants/devices you want to monitor
   - Follow the authorization process in the developer section

### 2. Getting Device Information

You'll need the following information about your devices:
   - **Device Serial Number (SN)**: This can be found in the Elekeeper console under "View Authorized Devices"
   - **Plant ID**: This is associated with your plant in the Elekeeper platform
   - **Device Type**: Select whether the device is a solar inverter or battery system

For detailed instructions on this process, refer to the SAJ Elekeeper API Documentation at the [SAJ International Developer Portal](https://intl-developer.saj-electric.com). The portal provides:

- API documentation
- Developer guides 
- Sample code
- File center with additional resources at https://intl-developer.saj-electric.com/fileCenter/index

If you are a plant owner and working with a third-party developer, you'll need to authorize their developer ID to access your plant data.

## Installation

### HACS (Recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance.
2. Click the HACS install button above or add this repository as a custom repository in HACS:
   - Go to HACS > Integrations > ⋮ > Custom repositories
   - Add `https://github.com/lowkey88/SAJMonitor` as a repository
   - Select "Integration" as the category
3. Click "Download" on the SAJ Monitor integration
4. Restart Home Assistant

### Manual Installation

1. Download the latest release from this repository
2. Create a `custom_components` directory in your Home Assistant configuration directory if it doesn't already exist
3. Extract the `saj_monitor` directory from the release into the `custom_components` directory
4. Restart Home Assistant

## Configuration

After installation, you'll need to configure the integration:

1. Go to Home Assistant > Settings > Devices & Services
2. Click "Add Integration" and search for "SAJ Monitor"
3. You'll be prompted to enter your API credentials:
   - **App ID**: Enter the App ID obtained from the Elekeeper developer portal
   - **App Secret**: Enter the App Secret obtained from the Elekeeper developer portal
4. Click "Submit" to validate your credentials
5. Next, you'll be prompted to add your device:
   - **Name**: Enter a friendly name for your device (e.g., "Rooftop Solar")
   - **SN**: Enter the device Serial Number from the Elekeeper console
   - **Plant ID**: Enter the Plant ID from the Elekeeper console
   - **Type**: Select either "solar" or "battery" depending on your device type
6. Click "Submit" to add the device
7. You can add additional devices by repeating the process

After adding your devices, the integration will create entities for each device, and you can start monitoring your SAJ solar inverters and battery systems in Home Assistant.

## Available Sensors

The integration provides the following sensors:

### Common Sensors (Both Solar and Battery)
- Current Power
- Today's Generation
- Total Generation
- Grid Power
- Grid Status
- Operating Status
- Home Load Power

When eSolar SEC load-monitoring data is available, Home Load Power includes source metadata:
- `source: sec` and `estimated: false` for official SEC load data
- fallback/estimated source attributes when inverter-derived estimates are used

### Solar Inverter Specific Sensors
- PV1/PV2 Power, Voltage, and Current
- Grid Phase (R, S, T) Power, Voltage, Current, and Frequency
- Inverter Temperature

### Battery System Specific Sensors
- Battery Level
- Battery Power
- Battery Status
- Battery Temperature
- Today's Battery Charge/Discharge
- Total Battery Charge/Discharge
- Battery Efficiency
- Backup Load Power (if available)

### Environmental Impact Sensors
- CO2 Reduction
- Equivalent Trees
- Estimated Annual Production
- Estimated Annual Savings

### eSolar SEC / Load-Monitoring Sensors

For plants with an eSolar SEC module and working plant-level `secData` access, the integration exposes additional load and self-consumption sensors:

- SEC Last Data Time
- SEC Data Age
- SEC Load Self Consumed Energy
- SEC Self Consumption Rate
- SEC Solar Offset Rate
- Estimated TNB ToU NEM Cost Today

The TNB cost sensor is intentionally marked as an estimate. The SAJ SEC endpoint currently provides daily total import/export energy, but not peak/off-peak bucketed energy. The integration therefore uses a configurable/bill-derived blended Domestic ToU + NEM model rather than claiming to reproduce the exact monthly TNB bill.

The cost estimate includes:
- import energy from SEC `buyEnergy`
- export/NEM credit from SEC `sellEnergy`
- peak/off-peak blended energy rate
- AFA, capacity, network, retail, service tax, and KWTBB assumptions

The payable value is floored at RM0 so a high-export day does not show a negative bill payable.

## Troubleshooting

If you encounter any issues:

1. Check the Home Assistant logs for error messages
2. Make sure your SAJ Developer API credentials are correct
3. Verify that your device serial numbers and plant IDs are correct
4. Confirm that you've completed the authorization process on the SAJ Elekeeper platform
5. Ensure your developer account has permissions to access the devices you're trying to monitor
6. Restart Home Assistant after making changes to the integration

For eSolar SEC users:
- Use the plant-level `secData` endpoint for official load-monitoring data.
- Continue using the inverter/device SN for realtime, history, and device-info endpoints.
- Do not assume the SEC module SN itself will work with realtime/history APIs; some accounts return authorization or "No inverter with this SN" errors for direct SEC SN calls even when plant-level `secData` works.
- Check the Home Load Power entity attributes to confirm whether the value is official SEC data (`source: sec`, `estimated: false`) or an inverter-derived fallback estimate.

If you receive authentication errors, you may need to:
- Check if your developer account is still active
- Re-authorize your resources in the Elekeeper portal
- Verify you're using the international node: https://intl-developer.saj-electric.com (for international users except Europe)
- European users should use: https://developer.electric.com

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release notes and version history.

## Reporting Issues

If you're experiencing problems, please create an issue on GitHub with the following information:
1. A detailed description of the problem
2. Your Home Assistant version
3. The error message from your logs
4. Screenshots if applicable

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
