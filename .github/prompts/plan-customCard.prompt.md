## Plan: Fronius TDC Custom Lovelace Card

Implement a purpose-built Lovelace card that presents all Time-of-Use schedules in a compact,
editable table and exposes add/delete operations — without requiring the user to hunt for
individual switch/number/select/time entities across the HA entity registry.

---

### Design constraints

- **Single source of truth**: The card reads entity states from `hass.states` and writes
  exclusively through `hass.callService()`; it never calls the inverter directly.
- **No server-side additions**: All card code lives in a single bundled JavaScript file
  served by HA's HTTP layer directly from the integration package.
- **HA-native UX**: Use native HA custom-element patterns (`ha-switch`, `ha-select`,
  `ha-textfield`, etc.) so the card inherits the active theme automatically.
- **Single repository**: Card source and build tooling live in this repository alongside
  the Python integration; `hacs.json` remains `type: "integration"` — no second HACS entry
  required.
- **Pre-built bundle committed on release**: The Rollup output
  `custom_components/fronius_tdc/www/fronius-tdc-card.js` is committed only during the
  release CI step so HACS installers always receive a ready-to-use file.

---

### Repository layout (within this repository)

```
fronius_tdc/                          # repository root
├── hacs.json                         # type: "integration" (unchanged)
├── package.json                      # card build tooling
├── tsconfig.json
├── rollup.config.js
├── card/
│   ├── src/
│   │   ├── fronius-tdc-card.ts       # card entry-point and LitElement root
│   │   ├── types.ts                  # TypeScript-shaped schedule/entity interfaces
│   │   ├── entity-resolver.ts        # maps config-entry ID to entity IDs
│   │   ├── components/
│   │   │   ├── schedule-row.ts       # one editable schedule row
│   │   │   └── add-schedule-dialog.ts  # modal for new schedule
│   │   └── utils/
│   │       ├── time.ts               # HH:MM ↔ Date conversion helpers
│   │       └── weekdays.ts           # weekday constant ordering
│   └── tests/
│       ├── entity-resolver.test.ts
│       ├── schedule-row.test.ts
│       └── add-schedule-dialog.test.ts
└── custom_components/
    └── fronius_tdc/
        └── www/
            └── fronius-tdc-card.js   # Rollup output — committed only on release
```

---

### Steps

#### 1. Bootstrap build toolchain in the existing repository

- Add `package.json` at the repository root with dev dependencies:
  `lit`, `@web/test-runner`, `@web/test-runner-playwright`, `rollup`,
  `@rollup/plugin-typescript`, `@rollup/plugin-node-resolve`,
  `rollup-plugin-minify-html-literals`, `typescript`.
- Add `package.json` scripts: `build`, `watch`, `test:card`, `lint:card`.
- Configure `tsconfig.json` targeting ES2019 with `"useDefineForClassFields": false`
  (required for LitElement decorators); set `rootDir` to `card/src`.
- Configure `rollup.config.js` to resolve `card/src/fronius-tdc-card.ts` and output to
  `custom_components/fronius_tdc/www/fronius-tdc-card.js` (IIFE, minified in CI).
- Add `custom_components/fronius_tdc/www/` to `.gitignore`; the built file is only
  committed by the release workflow.

#### 2. Register static path in `custom_components/fronius_tdc/__init__.py`

- In `async_setup_entry`, register the `www/` directory as a static HTTP path:
  ```python
  hass.http.register_static_path(
      "/fronius_tdc/fronius-tdc-card.js",
      hass.config.path("custom_components/fronius_tdc/www/fronius-tdc-card.js"),
      cache_headers=False,
  )
  ```
- The card is then reachable at `http://<ha>/fronius_tdc/fronius-tdc-card.js`.
- Document the one-time Lovelace resource step in `README.md`:
  ```yaml
  url: /fronius_tdc/fronius-tdc-card.js
  type: module
  ```
- No automatic resource injection is implemented; manual dashboard resource registration
  is sufficient and avoids requiring storage-mode Lovelace.

#### 3. Define TypeScript interfaces (`card/src/types.ts`)

```ts
interface TouSchedule {
  active: boolean;
  scheduleType: "CHARGE_MAX" | "CHARGE_MIN" | "DISCHARGE_MAX" | "DISCHARGE_MIN";
  power: number;         // watts
  startTime: string;     // "HH:MM"
  endTime: string;       // "HH:MM"
  weekdays: Record<"Mon"|"Tue"|"Wed"|"Thu"|"Fri"|"Sat"|"Sun", boolean>;
}

interface CardConfig {
  type: string;
  config_entry_id: string;   // HA config entry ID for the Fronius inverter
}
```

#### 4. Entity resolver (`card/src/entity-resolver.ts`)

- Accept `hass` object + `config_entry_id`.
- Scan `hass.states` to find all entities whose `attributes.config_entry_id` matches
  (or alternatively whose `entity_id` follows the integration's naming convention:
  `switch.fronius_tdc_schedule_N_*`, `number.fronius_tdc_schedule_N_power`,
  `select.fronius_tdc_schedule_N_type`, `time.fronius_tdc_schedule_N_start/end`).
- Return a structured map:
  ```ts
  type EntityMap = {
    scheduleCount: number;
    activeSwitch:    (n: number) => string;   // entity ID
    typeSelect:      (n: number) => string;
    powerNumber:     (n: number) => string;
    startTime:       (n: number) => string;
    endTime:         (n: number) => string;
    weekdaySwitch:   (n: number, day: string) => string;
  };
  ```
- Derive `scheduleCount` from the highest N found.
- Unit-test with a mock `hass.states` snapshot.

#### 5. Card root element (`card/src/fronius-tdc-card.ts`)

- Extend `LitElement`, implement the HA card contract:
  - `static getConfigElement()` → editor element (step 8).
  - `static getStubConfig()` → `{ type: "custom:fronius-tdc-card" }`.
  - `set hass(h)` stores `this._hass` and triggers `requestUpdate()`.
  - `setConfig(config)` validates that `config_entry_id` is present.
- `render()` produces a `<ha-card>` containing:
  - Header row (column labels: Active, Type, Power, Start, End, Mon–Sun, ⋮).
  - One `<fronius-schedule-row>` per discovered schedule.
  - Footer "＋ Add schedule" button that opens `<add-schedule-dialog>`.
- Style with CSS custom properties (`--primary-color`, `--card-background-color`, etc.)
  so the card respects the active HA theme.
- Provide a `static styles` block; do not use external CSS files.

#### 6. Schedule row component (`card/src/components/schedule-row.ts`)

Each row is a LitElement that receives `hass`, `entityMap`, and `index` as properties.

| Column | Element | Write path |
|---|---|---|
| Active | `<ha-switch>` | `hass.callService("homeassistant", "turn_on/turn_off", {entity_id})` |
| Type | `<ha-select>` | `hass.callService("select", "select_option", {entity_id, option})` |
| Power | `<ha-textfield>` (number) | `hass.callService("number", "set_value", {entity_id, value})` |
| Start | `<ha-time-input>` | `hass.callService("time", "set_value", {entity_id, time})` |
| End | `<ha-time-input>` | `hass.callService("time", "set_value", {entity_id, time})` |
| Weekdays | 7× `<ha-icon-button>` | `hass.callService("homeassistant", "turn_on/turn_off", {entity_id})` |
| Delete | `<ha-icon-button>` (mdi:delete) | `hass.callService("fronius_tdc", "remove_schedule", {config_entry_id, index})` |

- Read values from `hass.states[entityId].state` (and `.attributes` where needed).
- Debounce text field changes by 600 ms before writing.
- Show a spinner on the affected cell while the service call is in flight.
- On service error, revert the cell to its pre-edit value and surface an `<ha-alert>`.

#### 7. Add-schedule dialog (`card/src/components/add-schedule-dialog.ts`)

- Extend `LitElement`; use `<ha-dialog>` as root.
- Form fields mirror the TOU schedule schema: Type (select), Power (number),
  Start/End (time inputs), Weekdays (toggles), Active (switch, default off).
- "Save" button calls:
  ```ts
  hass.callService("fronius_tdc", "add_schedule", {
    config_entry_id,
    schedule_type,
    power,
    start_time,
    end_time,
    weekdays,
    active,
  });
  ```
- Validate locally before calling the service: non-empty type, start < end, power in range.
- Close dialog on success; show inline error on failure.

#### 8. Weekday utils (`card/src/utils/weekdays.ts`)

- Export `WEEKDAY_KEYS: readonly string[]` in canonical Mon–Sun order.
- Export short-label map (`{ Mon: "M", Tue: "T", ... }`) for compact display.

#### 9. Card editor element (visual config)

- Implement `<fronius-tdc-card-editor>` as a LitElement form.
- Only one required field: `config_entry_id` — render a `<ha-select>` populated by
  calling the HA WebSocket `config/entity_registry/list` and filtering by domain
  `fronius_tdc`, or fall back to a free-text `<ha-textfield>`.
- Register with `customCards` array in the card bundle so HA picks up the editor.

#### 10. Build and bundle

- `rollup.config.js` resolves `card/src/fronius-tdc-card.ts` →
  `custom_components/fronius_tdc/www/fronius-tdc-card.js` (IIFE, minified in CI).
- Include a `customElements.define("fronius-tdc-card", FroniusTdcCard)` call at the
  bottom of the bundle (guard with `customElements.get` check for safe re-load).
- Set `customCards` registration block:
  ```js
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "fronius-tdc-card",
    name: "Fronius TDC Scheduler",
    description: "Edit Time-of-Use schedules for your Fronius inverter.",
    preview: true,
  });
  ```

#### 11. Tests

- Use `@web/test-runner` with Playwright (Chromium) for component tests.
- `card/tests/entity-resolver.test.ts`:
  - Mock `hass.states` with 3 schedules; assert correct entity ID resolution.
  - Assert `scheduleCount` equals 3.
  - Assert empty states returns `scheduleCount = 0`.
- `card/tests/schedule-row.test.ts`:
  - Render a row with fixture state; assert rendered values match.
  - Simulate `ha-switch` change; assert `callService` called with correct entity and domain.
  - Simulate delete button; assert `fronius_tdc.remove_schedule` called with correct index.
- `card/tests/add-schedule-dialog.test.ts`:
  - Assert "Save" disabled when type not selected.
  - Assert service called with correct payload on valid submit.
  - Assert inline error displayed when service rejects.

#### 12. Update release workflow

- Extend the existing `.github/workflows/release.yml` (or create it):
  - Add `npm ci && npm run build` before the Python packaging steps.
  - Commit the built `custom_components/fronius_tdc/www/fronius-tdc-card.js` into the
    release tag so HACS users receive the compiled file.
- Update `README.md` with:
  - One-time Lovelace resource registration step (Settings → Dashboards → Resources).
  - Dashboard card YAML example:
    ```yaml
    type: custom:fronius-tdc-card
    config_entry_id: <your_entry_id>
    ```
  - Screenshot placeholder.

---

### Relevant files

- `card/src/fronius-tdc-card.ts` — card root.
- `card/src/types.ts` — shared TypeScript interfaces.
- `card/src/entity-resolver.ts` — entity-ID discovery logic.
- `card/src/components/schedule-row.ts` — per-schedule editable row.
- `card/src/components/add-schedule-dialog.ts` — new-schedule modal.
- `card/src/utils/weekdays.ts` — weekday ordering helpers.
- `rollup.config.js` — build configuration (repository root).
- `package.json` — build/test/lint scripts (repository root).
- `card/tests/entity-resolver.test.ts` — resolver unit tests.
- `card/tests/schedule-row.test.ts` — row component tests.
- `card/tests/add-schedule-dialog.test.ts` — dialog component tests.
- `custom_components/fronius_tdc/www/fronius-tdc-card.js` — compiled output (gitignored; committed only by release CI).
- `custom_components/fronius_tdc/__init__.py` — registers static HTTP path for the card bundle.
- `.github/workflows/release.yml` — builds JS bundle and includes it in the release tag.

---

### Verification

1. `npm run build` produces `custom_components/fronius_tdc/www/fronius-tdc-card.js` without errors.
2. `npm run test:card` — all component tests pass.
3. `npm run lint:card` — no ESLint/TypeScript errors.
4. Python test suite unaffected: `pytest` continues to pass.
5. Manual HA test: register `/fronius_tdc/fronius-tdc-card.js` as a Lovelace resource →
   add card with `config_entry_id` → verify all schedules render and edits round-trip correctly.
6. Confirm HACS validation passes with `type: "integration"` (run `hacs-action` locally or via CI).
