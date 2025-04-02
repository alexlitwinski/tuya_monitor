# Tuya Monitor for Home Assistant

A simple integration to monitor property values from Tuya devices using the Tuya Cloud API.

## Installation

### HACS Installation
1. Make sure you have [HACS](https://hacs.xyz/) installed
2. Add this repository as a custom repository in HACS
3. Install the "Tuya Monitor" integration via HACS
4. Restart Home Assistant

### Manual Installation
1. Copy the `custom_components/tuya_monitor` directory from this repository into the `custom_components` directory of your Home Assistant installation
2. Restart Home Assistant

## Setup

### Prerequisites
You need to have:
1. A Tuya IoT Platform account
2. A Tuya IoT Cloud project
3. The following credentials:
   - Client ID
   - Client Secret
   - Access Token
   - Region (us, eu, cn, in)

If you don't have these credentials, follow Tuya's documentation to create a project and get your API credentials.

### Adding the Integration
1. In Home Assistant, go to **Configuration** → **Integrations**
2. Click **+ ADD INTEGRATION**
3. Search for "Tuya Monitor" and select it
4. Enter your Tuya API credentials

### Adding Devices to Monitor
1. Go to **Configuration** → **Integrations**
2. Find the "Tuya Monitor" integration and click **Configure**
3. Select "Add Device"
4. Enter:
   - **Device ID**: Your Tuya device ID (also known as Virtual ID or DeviceID)
   - **Properties**: Comma-separated list of property codes to monitor (e.g., "residual_electricity,power")
   - **Scan Interval**: How often to check for updates (in seconds)
5. Click **Submit**

## Usage
Once set up, the integration will create sensor entities for each device property you specified. The sensors will update according to the scan interval you configured.

Example sensor name: `sensor.tuya_DEVICEID_PROPERTY`

## Troubleshooting
- Check the Home Assistant logs for errors
- Verify that your API credentials are correct
- Make sure the device ID and property codes you entered are valid

## License
This project is licensed under the MIT License - see the LICENSE file for details.
