# Fronius Gen24 Time Dependent Controls

Home Assistant integration for controlling Fronius Gen24 inverters with Time of Use (TOU) schedule management.

## Features

- Read and control Time of Use (TOU) schedules
- Edit TOU fields per rule directly in Home Assistant:
  - Active state
  - Weekday enable flags (Mon-Sun)
  - Power setpoint
  - Schedule type
  - Start and end times
- Add and remove TOU rules via integration services
- Change SoC settings (Battery Reserve, Max Charge, etc)
- Set self-consumption optimisation target

## TOU Editing Model

- The inverter is the source of truth for schedules.
- This integration does not persist local schedule state or migrations.
- Entity identity is based on inverter rule identity (or deterministic fallback identity) to reduce entity churn when order changes.

## TOU Services

- `fronius_tdc.add_schedule`
  - Required fields: `active`, `schedule_type`, `power`, `start`, `end`, `weekdays`
  - Optional: `config_entry_id` when multiple inverters are configured
- `fronius_tdc.remove_schedule`
  - Target by `rule_id` (preferred) or `index`
  - Optional: `config_entry_id`

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
