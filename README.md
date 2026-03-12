# Fronius Gen24 Time Dependent Controls

Home Assistant integration for controlling Fronius Gen24 inverters with Time of Use (TOU) schedule management.

## Features

- Read and control Time of Use (TOU) schedules
- Edit TOU schedule fields directly from Home Assistant entities:
	- Active toggle
	- Weekday toggles (Mon-Sun)
	- Power (number entity)
	- Schedule type (select entity)
	- Start/End times (time entities)
- Add and remove TOU schedules via services
- Change SoC settings (Battery Reserve, Max Charge, etc)
- Set self-consumption optimisation target

## Time of Use Editing

Each schedule is exposed as a group of entities under the same device. You can edit
existing rules from the Home Assistant UI using:

- `switch.*_schedule_<index>_active` for enabled state
- `switch.*_schedule_<index>_mon` ... `switch.*_schedule_<index>_sun` for weekdays
- `number.*_schedule_<index>_power` for schedule power in watts
- `select.*_schedule_<index>_schedule_type` for charge/discharge mode
- `time.*_schedule_<index>_start_time` and `time.*_schedule_<index>_end_time`

Time values are validated as strict 24-hour `HH:MM` and invalid values are rejected.

## Schedule Services

Use these services for create/delete operations:

- `fronius_tdc.add_schedule`
- `fronius_tdc.remove_schedule`

Example add call:

```yaml
service: fronius_tdc.add_schedule
data:
	schedule_type: CHARGE_MAX
	start: "08:00"
	end: "18:00"
	weekdays: [Mon, Tue, Wed, Thu, Fri]
	active: true
	power: 3000
```

Example remove call:

```yaml
service: fronius_tdc.remove_schedule
data:
	index: 0
```

If multiple Fronius entries are configured, include `config_entry_id` in service
calls.

## Data Ownership Model

The inverter is the single source of truth for TOU schedules.

- No local schedule persistence or migration state is stored by this integration.
- All updates use a full read-modify-write cycle against the inverter API.
- Add/remove operations reload the config entry so entity sets are refreshed cleanly.

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
