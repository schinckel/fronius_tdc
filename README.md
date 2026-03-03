# Fronius Gen24 Time Dependent Controls

Home Assistant integration for controlling Fronius Gen24 inverters with Time of Use (TOU) schedule management.

## Features

- Read and control Time of Use (TOU) schedules
- Monitor active schedules
- Enable/disable individual TOU entries
- Full digest authentication support for Fronius Gen24 web interface

## Installation

### Via HACS (Home Assistant Community Store)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Search for "Fronius Gen24 Time Dependent Controls"
4. Click Install

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
