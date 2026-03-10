## Plan: Editable TOU Rule Management

Implement full TOU rule management in Home Assistant by combining entity-based editing for existing rules with service-based create/delete operations, with inverter data as the only source of truth and no persistent local schedule state.

**Steps**
1. Phase 1: Data model and coordinator write API.
2. Add a canonical rule schema and helper utilities in `custom_components/fronius_tdc/tdc_coordinator.py`:
- Normalize and validate schedule payloads (required keys: `Active`, `ScheduleType`, `Power`, `TimeTable.Start`, `TimeTable.End`, `Weekdays`).
- Add time/weekday/type validators.
- Add deep-copy read-modify-write helper that updates one rule field without mutating unrelated rules.
- Keep write operations centralized in coordinator to preserve API contract (`POST /api/config/timeofuse` with full list).
3. Add coordinator mutation methods in `custom_components/fronius_tdc/tdc_coordinator.py`:
- `async_set_active(index_or_rule_id, active)` (existing method refactored onto shared helper).
- `async_set_power(index_or_rule_id, power)`.
- `async_set_schedule_type(index_or_rule_id, schedule_type)`.
- `async_set_start_time(index_or_rule_id, start)` and `async_set_end_time(index_or_rule_id, end)`.
- `async_set_weekday(index_or_rule_id, day, enabled)`.
- `async_add_schedule(schedule)`.
- `async_remove_schedule(index_or_rule_id)`.
4. Introduce stable rule identity in coordinator (depends on 2):
- Stop relying on list index as the external identity.
- Derive a stable `rule_id` from each refresh payload only (no disk/local persistence).
- Prefer inverter-provided metadata id (e.g., `_Id`) as canonical identity when available.
- If no explicit id exists, derive deterministic ephemeral identity from rule fields at refresh time, with collision handling.
- Expose helper methods to resolve `rule_id <-> index` for entities/services from current coordinator data.
5. Phase 2: Entity platforms for editable fields.
6. Refactor schedule entities to `EntityDescription`-style descriptors in `custom_components/fronius_tdc/const.py` plus platform files:
- Add schedule field descriptors for switch/number/select/time-like controls.
- Reuse one generic per-platform schedule entity class pattern.
7. Extend `custom_components/fronius_tdc/switch.py`:
- Keep `FroniusScheduleSwitch` for Active state.
- Add per-rule weekday switches (`Mon`..`Sun`) driven by descriptors.
- Use `rule_id`-based unique IDs instead of positional index.
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
12. Register integration services in `custom_components/fronius_tdc/__init__.py`:
- `fronius_tdc.add_schedule`.
- `fronius_tdc.remove_schedule`.
- Optional convenience: `fronius_tdc.duplicate_schedule` (excluded initially unless requested).
13. Add service schemas and handler wiring:
- Validate service payloads before coordinator calls.
- Resolve target rule by `rule_id` (and optionally index for compatibility).
14. Add service documentation file `custom_components/fronius_tdc/services.yaml` and update `custom_components/fronius_tdc/translations/en.json` with service fields/descriptions.
15. Handle entity lifecycle on rule count/order change:
- During coordinator refresh, detect rule set delta.
- Trigger config-entry reload only when needed to add/remove entities.
- Ensure unchanged rules preserve unique IDs when order changes.
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
- Reorder rules externally (in inverter UI), refresh, and verify unchanged rules keep stable entity IDs.

**Decisions**
- Included scope: edit existing rules + create new rules + delete rules.
- Excluded scope: migration or persistence of local schedule state (inverter is source of truth).
- Architectural choice: entities for per-rule field editing; services for create/delete to align with HA patterns.
- Correctness requirement: avoid index-only identity so create/delete/reorder does not churn entity IDs.

**Further Considerations**
1. Rule identity source recommendation:
- Option A: retain inverter metadata id (preferred if always present).
- Option B: deterministic hash over immutable subset + runtime collision handling.
- Option C: continue index-based IDs (not recommended; regression risk).
2. Time editor recommendation:
- Option A: `time` entities if platform support is straightforward.
- Option B: validated `text` entities for `HH:MM` if `time` platform support is limited.
3. Entity churn strategy recommendation:
- Option A: config entry reload on count/order delta (simple, reliable).
- Option B: incremental entity add/remove bookkeeping (more complex, less reload churn).
