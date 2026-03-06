# Fronius Gen24 Time Dependent Controls

Home Assistant integration for controlling Fronius Gen24 inverters with Time of Use (TOU) schedule management.

## Features

- Read and control Time of Use (TOU) schedules
- Change SoC settings (Battery Reserve, Max Charge, etc)
- Set self-consumption optimisation target

## Limitations

- Supports only local Customer/Technician username/password authentication, SSO from SolarWeb not supported.

## Installation

### Via HACS (Home Assistant Community Store)

1. Open HACS in Home Assistant
2. Click the three-dot menu and select "Custom repositories"
3. Paste `https://github.com/schinckel/fronius_tdc` in the repository URL field
4. Select "Integration" as the category
5. Click Add
6. Click the close (X) button.
7. Go to "Integrations"
8. Search for "Fronius Gen24 Time Dependent Controls"
9. Click Install

### Manual Installation

1. Download the repository
2. Copy `custom_components/fronius_tdc` to your `custom_components` folder
3. Restart Home Assistant

## Configuration

Add the integration via Home Assistant UI (Settings → Devices & Services → Create Integration).

You'll need:
- **IP Address/Hostname**: The local IP or hostname of your Fronius inverter
- **HTTP Port**: Port number (default: 80)
- **Username**: Inverter web interface username (e.g., 'customer' or 'technician')
- **Password**: Inverter web interface password

## Support

For issues, feature requests, or questions, please visit the [GitHub repository](https://github.com/schinckel/fronius_tdc/issues).
