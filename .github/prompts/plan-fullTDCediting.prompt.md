## Plan: Editable TOU Rule Management

Implement full TOU rule management in Home Assistant by combining entity-based editing for existing rules with service-based create/delete operations, with inverter data as the only source of truth and no persistent local schedule state.

**Steps**
1. Phase 1: Data model and coordinator write API.
- Refactor existing coordinator code to treat inverter schedule list as source of truth, eliminating any local state or caching of schedules beyond the current fetched list.
- Ensure all schedule updates go through coordinator methods that perform a full read-modify-write cycle against the inverter API, sending the complete updated schedule list on each change to maintain API contract and avoid partial update issues.
- Refactor existing Active toggle method to this new pattern as a starting point for the coordinator write API. This will involve deep-copying the current schedule list, modifying the relevant field, and sending the entire updated list back to the inverter.
- This approach ensures that any concurrent changes (e.g. from another client or manual inverter changes) are correctly handled on the next refresh cycle, as the coordinator will always fetch the latest state from the inverter before applying any updates.
- This also simplifies the coordinator logic by centralizing all write operations and ensuring a consistent update pattern for all schedule modifications, which will be crucial as we add more editable fields and create/delete functionality in later phases.
- This phase will not introduce any new entity types or service handlers; it will focus solely on establishing a robust and consistent coordinator write API that can be used by the existing Active toggle and future editable fields. The UI/UX for editing other fields and adding/removing schedules will be implemented in subsequent phases after the coordinator API is solidified.
- This phased approach allows us to ensure a stable foundation for schedule management before exposing more complex editing capabilities to users, and it minimizes the risk of introducing bugs or inconsistencies in the schedule handling logic.
- This also allows for incremental testing and validation of the coordinator logic before we add the complexity of new entity types and service handlers, ensuring that we have a reliable mechanism for updating schedules in place before we build on top of it.
2. Add a canonical rule schema and helper utilities in `custom_components/fronius_tdc/tdc_coordinator.py`:
- Normalize and validate schedule payloads (required keys: `Active`, `ScheduleType`, `Power`, `TimeTable.Start`, `TimeTable.End`, `Weekdays`).
- Add time/weekday/type validators.
- Add deep-copy read-modify-write helper that updates one rule field without mutating unrelated rules.
- Keep write operations centralized in coordinator to preserve API contract (`POST /api/config/timeofuse` with full list).
3. Add coordinator mutation methods in `custom_components/fronius_tdc/tdc_coordinator.py`:
- `async_set_active(index, active)` (existing method refactored onto shared helper).
- `async_set_power(index, power)`.
- `async_set_schedule_type(index, schedule_type)`.
- `async_set_start_time(index, start)` and `async_set_end_time(index_or_rule_id, end)`.
- `async_set_weekday(index, day, enabled)`.
- `async_add_schedule(schedule)`.
- `async_remove_schedule(index)`.
5. Phase 2: Entity platforms for editable fields.
- Implement stable unique ID strategy for schedule entities based on rule index or a generated rule ID that remains stable across reorder/add/remove operations (e.g. `fronius_tdc.schedule.{rule_id}.power`).
6. Refactor schedule entities to `EntityDescription`-style descriptors in `custom_components/fronius_tdc/const.py` plus platform files:
- Add schedule field descriptors for switch/number/select/time-like controls.
- Reuse one generic per-platform schedule entity class pattern.
- Add entity descriptions with value mapping and validation metadata (e.g. min/max/step for power, option labels for schedule type, etc).
7. Extend `custom_components/fronius_tdc/switch.py`:
- Keep `FroniusScheduleSwitch` for Active state.
- Add per-rule weekday switches (`Mon`..`Sun`) driven by descriptors.
8. Extend `custom_components/fronius_tdc/number.py`:
- Add schedule power number entity per rule.
- Add conservative min/max and step constraints aligned with existing battery number conventions.
9. Extend `custom_components/fronius_tdc/select.py`:
- Add schedule type select per rule using `SCHEDULE_TYPE_LABELS`.
10. Implement validated time editing surface (depends on 2, parallel with 6-9):
- Add dedicated start/end time entities in `custom_components/fronius_tdc/time.py`.
- Validate all values as strict 24h `HH:MM` at entity and coordinator boundaries before write.
- Reject invalid times with clear errors; do not send invalid payloads to inverter.
- Register `time` platform in `custom_components/fronius_tdc/__init__.py` `PLATFORMS`.
11. Phase 3: Create/delete actions and lifecycle.
- Implement add/remove services that accept necessary fields (e.g. type, time, days) and reasonable defaults (e.g. inactive, 0 power) for missing fields.
- Service handlers call coordinator mutators to update schedule list and trigger full refresh.
- Ensure add/remove operations preserve unrelated rules and maintain stable IDs for unaffected rules to minimize entity churn.
- Consider entity churn strategy for add/remove (full reload vs incremental bookkeeping) and implement accordingly.
-  Implement coordinator-side validation for service payloads to ensure only valid schedules are created/updated.
- Implement clear error handling and user feedback for invalid service calls (e.g. missing required fields, invalid time format, out-of-range power).
- Update coordinator and entity state after add/remove to reflect changes in HA UI without requiring manual refresh.
12. Register integration services in `custom_components/fronius_tdc/__init__.py`:
- `fronius_tdc.add_schedule`.
- `fronius_tdc.remove_schedule`.
- Optional convenience: `fronius_tdc.duplicate_schedule` (excluded initially unless requested).
13. Add service schemas and handler wiring:
- Validate service payloads before coordinator calls.
14. Add service documentation file `custom_components/fronius_tdc/services.yaml` and update `custom_components/fronius_tdc/translations/en.json` with service fields/descriptions.
16. Phase 4: Tests and docs.
17. Expand `tests/test_tdc_coordinator.py`:
- Add unit tests for each new coordinator mutator.
- Add validation failure tests (invalid time format/value, invalid type, missing weekdays, out-of-range power).
- Add add/remove tests preserving unrelated rules.
- Add stable identity tests across reordering/add/remove refresh cycles.
18. Expand platform tests:
- `tests/test_switch.py`: weekday schedule switches, rule_id unique IDs, add/remove/reorder resilience.
- `tests/test_number.py`: schedule power entities and setter path.
- `tests/test_select.py`: schedule type entities and option mapping.
- Add `tests/test_time.py` for start/end editing, including invalid time rejection and boundary values (`00:00`, `23:59`).
19. Expand lifecycle tests in `tests/test_init.py`:
- Service registration/unregistration.
- Platform forwarding updates if new platform (`time` or `text`) is introduced.
20. Update `README.md` with user-facing usage:
- How to edit rule fields.
- How to add/remove schedules via service calls.
- Explicit note that inverter remains source of truth; no migration/local persistence required.

**Relevant files**
- `/workspaces/fronius_tdc/custom_components/fronius_tdc/tdc_coordinator.py` — add rule validators, stable identity mapping, and all write mutators.
- `/workspaces/fronius_tdc/custom_components/fronius_tdc/const.py` — add descriptor definitions/options/constants for editable schedule fields.
- `/workspaces/fronius_tdc/custom_components/fronius_tdc/switch.py` — keep Active switch and add weekday rule switches via descriptors.
- `/workspaces/fronius_tdc/custom_components/fronius_tdc/number.py` — add schedule Power number entities.
- `/workspaces/fronius_tdc/custom_components/fronius_tdc/select.py` — add schedule type select entities.
- `/workspaces/fronius_tdc/custom_components/fronius_tdc/time.py` or `/workspaces/fronius_tdc/custom_components/fronius_tdc/text.py` — start/end editors.
- `/workspaces/fronius_tdc/custom_components/fronius_tdc/__init__.py` — register service handlers and new platform(s).
- `/workspaces/fronius_tdc/custom_components/fronius_tdc/services.yaml` — service schemas for add/remove.
- `/workspaces/fronius_tdc/custom_components/fronius_tdc/translations/en.json` — service strings and entity labels.
- `/workspaces/fronius_tdc/tests/test_tdc_coordinator.py` — mutator, validation, identity, add/remove tests.
- `/workspaces/fronius_tdc/tests/test_switch.py` — schedule switch suite expansion.
- `/workspaces/fronius_tdc/tests/test_number.py` — schedule power number tests.
- `/workspaces/fronius_tdc/tests/test_select.py` — schedule type select tests.
- `/workspaces/fronius_tdc/tests/test_init.py` — platform + service lifecycle coverage.
- `/workspaces/fronius_tdc/README.md` — feature documentation.

**Verification**
1. Run focused unit tests: `pytest tests/test_tdc_coordinator.py tests/test_switch.py tests/test_number.py tests/test_select.py tests/test_init.py`.
2. Run full test suite: `pytest`.
3. Run lint/static checks via repository script: `scripts/lint`.
4. Manual HA validation in dev config:
- Confirm each existing schedule exposes editable fields (active/power/type/time/days).
- Create a schedule via service and verify entities appear after refresh/reload.
- Delete a schedule via service and verify entities disappear cleanly.

**Decisions**
- Included scope: edit existing rules + create new rules + delete rules.
- Excluded scope: migration or persistence of local schedule state (inverter is source of truth).
- Architectural choice: entities for per-rule field editing; services for create/delete to align with HA patterns.

**Further Considerations**
2. Time editor recommendation:
- Option A: `time` entities if platform support is straightforward.
- Option B: validated `text` entities for `HH:MM` if `time` platform support is limited.
3. Entity churn strategy recommendation:
- Option A: config entry reload on count/order delta (simple, reliable).
- Option B: incremental entity add/remove bookkeeping (more complex, less reload churn).
