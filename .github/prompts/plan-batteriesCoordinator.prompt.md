# Plan: Create Batteries Configuration Coordinator

## TL;DR
Create a new `FroniusBatteriesCoordinator` for managing battery settings via the `/api/config/batteries` endpoint. This will support mixed entity types (switches for booleans, number inputs for integers, select for enums, sensors for read-only state). Data comes from a single configuration object. The endpoint is write-focused but may support reads—we'll implement discovery logic to test feasibility.

---

## Decisions
- **Separate Coordinator**: New `FroniusBatteriesCoordinator` class (not integrated with existing TOU coordinator)
- **Read Strategy**: Attempt to read from same endpoint; if unavailable, store last written values locally
- **Data Structure**: Single configuration object (not a list)
- **Entity Types**:
  - `switch.py` - boolean configs
  - `number.py` - numeric inputs (integers)
  - `select.py` - enum configs (HYB_EM_MODE, BAT_M0_SOC_MODE)
  - `sensor.py` - optional read-only state (if endpoint supports reads)

---

## Steps

### Phase 1: Coordinator Setup
1. **Create constants in `const.py`**
   - `ENDPOINT_BATTERIES = "/api/config/batteries"`
   - Define dict mapping for entity types per key (for platform setup)
   - Example: `BATTERY_CONFIG_KEYS = {"HYB_EM_MODE": "select", "HYB_EM_POWER": "number", ...}`

2. **Create `FroniusBatteriesCoordinator` class in new file `batteries_coordinator.py`**
   - Inherit from `DataUpdateCoordinator[dict]` (single object, not list)
   - Implement `_blocking_get()` - attempt GET to endpoint; gracefully handle unsupported reads
   - Implement `_blocking_post(config_dict)` - write full config back
   - Implement `_async_update_data()` - call blocking_get with proper exception handling
   - Implement async action methods for each config type:
     - `async_set_switch(key: str, value: bool)`
     - `async_set_number(key: str, value: int)`
     - `async_set_select(key: str, value: str)`
   - Read-modify-write pattern: fetch current state (or use cached), modify one key, push back

3. **Initialize in `__init__.py`**
   - Create `FroniusBatteriesCoordinator` instance alongside TOU coordinator
   - Add first refresh and error handling
   - Add `Platform.SWITCH`, `Platform.NUMBER`, `Platform.SELECT` to PLATFORMS list

---

### Phase 2: Platform Implementations (can run in parallel)

4. **Create `switch.py` for boolean configs**
   - Entity setup: `async_setup_entry()` creates switch per boolean key
   - Boolean keys: `HYB_EVU_CHARGEFROMGRID`, `HYB_BM_CHARGEFROMAC`
   - Implement `is_on` property (read from coordinator data)
   - Implement `async_turn_on()` → calls coordinator `async_set_switch()`
   - Implement `async_turn_off()` → calls coordinator `async_set_switch()`

5. **Create `number.py` for numeric inputs**
   - Entity setup: `async_setup_entry()` creates number per numeric key
   - Numeric keys: `HYB_EM_POWER`, `HYB_BM_PACMIN`
   - Set min/max constraints (if known; may need doc or discovery)
   - Implement `value` property (read from coordinator data)
   - Implement `async_set_value(value)` → calls coordinator `async_set_number()`
   - Additional keys: `HYB_BACKUP_CRITICALSOC`, `HYB_BACKUP_RESERVED`, `BAT_M0_SOC_MAX`, `BAT_M0_SOC_MIN`
     - Device class: `SensorDeviceClass.PERCENTAGE`
    - Unit: `PERCENTAGE`

6. **Create `select.py` for enum configs**
   - Entity setup: `async_setup_entry()` creates select per enum key
   - Enum keys: `HYB_EM_MODE` (options: 0/Automatic, 1/Manual), `BAT_M0_SOC_MODE` (options: manual, auto)
   - Implement `current_option` property
   - Implement `async_select_option(option)` → calls coordinator `async_set_select()`
   - Localize option displays (e.g., "Automatic" for 0, "Manual" for 1)

---

### Phase 4: Integration & Testing
8. **Update `manifest.json`** (if needed)
   - Ensure no new dependencies required

9. **Add tests** (parallel with platform implementation)
   - `test_batteries_coordinator.py` - test read/write flow, error handling
   - Update existing tests if needed

---

## Relevant Files
- `const.py` — Add ENDPOINT_BATTERIES, BATTERY_CONFIG_KEYS mapping
- `batteries_coordinator.py` — New coordinator class (template from coordinator.py)
- `__init__.py` — Register coordinator, add platforms
- `switch.py` — Extend or create for battery switches (template from switch.py)
- `number.py` — Create new platform for numeric inputs
- `select.py` — Create new platform for enum selections
- `sensor.py` — Optional, create if reads are supported
- `test_batteries_coordinator.py` — New test file

---

## Verification
1. **Coordinator initialization** — Confirm FroniusBatteriesCoordinator loads without errors
2. **Platform entity creation** — Verify switches/numbers/selects appear in Home Assistant UI
3. **Read testing** — Attempt coordinator `_async_update_data()` and confirm behavior (success or graceful failure)
4. **Write testing** — Set each entity type (switch on/off, number value, select option) and confirm POST is called
5. **State propagation** — Toggle/set entity, verify coordinator data updates and UI reflects change
6. **Error handling** — Test with invalid values, network errors; confirm no crashes

---

## Further Considerations
1. **Min/max constraints for number inputs**: Do numeric keys (HYB_EM_POWER, HYB_BM_PACMIN) have documented min/max ranges, or should we auto-discover them from API responses?
2. **Percentage validation**: Are percentage keys bound-checked on the device side (e.g., HYB_BACKUP_CRITICALSOC must be < HYB_BACKUP_RESERVED)?
3. **Startup behavior**: If reads fail, should we hide the entities or show them in an unknown state?
