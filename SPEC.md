# miareczkowanie.simon-lab.org — Titration Analysis App

## Goal

Web app to import pH–time CSV from base-dosing titrations of leach liquors (H₂SO₄). Convert time to dosed base, build theoretical H₂SO₄ model, subtract baseline, detect peaks, quantify metals. HTTPS on subdomain: **miareczkowanie.simon-lab.org**.

## Core Features

* CSV import with flexible column mapping.
* Unit handling: decimal comma or dot; `,` or `;` separators.
* User confirms:

  * Base concentration `C_b` (default 0.1 mol/L NaOH).
  * Pump rate `q` (default 1.0 mL/min) or map a “pump flow” column.
  * Initial sample volume `V₀` (default 100 mL).
  * Temperature `T` (default 25 °C).
* Compute cumulative base volume and moles; correct dilution.
* Plot: pH vs dosed base and vs time.
* User selects **start point** on the plot; all calculations ignore earlier rows.
* Auto-fit theoretical **H₂SO₄-only** curve using selected segment.
* Compute excess base Δ over the model; show Δ vs pH and its derivative.
* Peak finding and metal quantification before user-set cutoff (default pH 6.5).
* Export plots (PNG/SVG) and results (CSV/JSON). Session save/load.

## Data In/Out

### Input CSV

* Required columns (user maps):

  * `pH`
  * `time` (s or min; auto-detected, user can set)
* Optional columns:

  * `pump_flow` (mL/min); if absent, use constant `q`.
  * `NaOH_conc` (mol/L) per row; if absent, use constant `C_b`.
* Parser tolerates headers, blank lines, localized decimals.

### Output

* Processed table per row:

  * `time`, `pH`, `V_b` (mL), `n_b` (mol), `B_meas` (mol/L, normalized to V₀), `[Na+]` (mol/L, with dilution), `B_model`, `ΔB`, `d(ΔB)/dpH`.
* Peaks table:

  * `peak_id`, `pH_start`, `pH_apex`, `pH_end`, `ΔB_step` (mol/L), `ν` (OH⁻/mol metal), `c_metal` (mol/L), `mg/L` (requires metal selection and molar mass), notes.

## Chemistry Model

Constants (editable in settings):

* `K_a2`(HSO₄⁻ ⇌ H⁺ + SO₄²⁻) default **1.2e−2** at 25 °C.
* `K_w` default **1.0e−14** at 25 °C. Optional `K_w(T)`.

Definitions (per row `i`):

* `H_i = 10^(−pH_i)`, `OH_i = K_w / H_i`.
* Fractions for sulfate:

  * `f(H) = (H + 2K_a2)/(H + K_a2)`.
* Delivered base:

  * If constant `q`: `V_b,i = q·t_i/60`. If variable flow: integrate trapezoidally.
  * `n_b,i = C_b,i · V_b,i / 1000`.
  * Normalized dose: `B_meas,i = n_b,i / (V₀/1000)`  \[mol/L “per initial volume”].
  * Instantaneous sodium with dilution:
    `Na_i = (C_b,i · V_b,i/1000) / ((V₀ + V_b,i)/1000) = C_b,i · V_b,i / (V₀ + V_b,i)`  \[mol/L].
* **H₂SO₄-only model** (electroneutrality):
  `Na_model = C_A · f(H) + OH − H`
  where `C_A` is total sulfate concentration \[mol/L].
* Convert `Na_model` back to normalized-dose axis:
  `B_model = Na_model / (1 − Na_model / C_b)`  (inverts dilution relation).
* **Estimating `C_A`**: for rows in the user-selected baseline window,
  `C_A,j = (Na_meas,j + H_j − OH_j)/f(H_j)`, with `Na_meas,j = B_meas,j / (1 + B_meas,j/C_b)`.
  Use robust median; outlier rejection by MAD.
* Excess base: `ΔB = B_meas − B_model`.

## Peak Detection and Quantification

* Smooth `ΔB(pH)` with Savitzky–Golay (default window 9 points, poly 3).
* Compute central-difference derivative `d(ΔB)/dpH`.
* Peaks: local maxima in derivative above SNR threshold; boundaries at nearest zero-crossings.
* Step size per peak: `ΔB_step = ΔB(pH_end) − ΔB(pH_start)`.
* Metal concentration from stoichiometry:

  * Choose `ν` per metal: Fe³⁺→3, Fe²⁺→2, Al³⁺→3, Ni²⁺→2, Co²⁺→2, Mn²⁺→2.
  * `c_metal = ΔB_step / ν`  \[mol/L].
  * `mg/L = c_metal · M` (molar mass from a built‑in table).
* Global cutoff: ignore rows with `pH > pH_cutoff` (default 6.5).

## UI/UX

* One-page flow with left panel controls, right panel plots.
* Steps:

  1. Upload CSV → column mapping → preview.
  2. Set `C_b`, `q`, `V₀`, `T`, `pH_cutoff`.
  3. Pick **start point** by clicking the plot; live refit of `C_A`.
  4. Plots:

     * pH vs normalized base: measured and H₂SO₄ model overlay.
     * ΔB vs pH with identified peaks.
     * d(ΔB)/dpH vs pH for visual peak localization.
  5. Metal assignment per peak: dropdown sets `ν` and molar mass.
  6. Export: PNG/SVG, CSV/JSON; Save session.

## API (FastAPI)

* `POST /api/import` → parses CSV, returns raw rows.
* `POST /api/compute` → body: settings + rows; returns processed table, model, peaks.
* `GET /api/constants` → Ka, Kw, molar masses.
* `POST /api/export` → returns CSV/JSON of results.
* Limits: CSV ≤ 10 MB; rows ≤ 200k.

## Algorithms and Numerics

* Time integration: trapezoidal.
* Robust `C_A` fit: median of early-window estimates with MAD filter (k=3).
* Savitzky–Golay via SciPy; all numeric in double precision.
* Peak detection: SciPy `find_peaks` on derivative with height and prominence settings; defaults exposed in UI.

## Technology

* Frontend: React + TypeScript + Vite, Plotly.js, Zustand (state), PapaParse.
* Backend: Python 3.11, FastAPI, Uvicorn, NumPy, SciPy, Pandas.
* Packaging: Docker. Reverse proxy: Nginx.
* TLS: Let’s Encrypt via certbot with auto‑renew.
* Domain: `miareczkowanie.simon-lab.org` A/AAAA to server; Nginx serves HTTPS and proxies to Uvicorn.

## Security and Privacy

* HTTPS only, HSTS, gzip off for JSON if needed, CORS locked to subdomain.
* File type and size checks, streaming parse, no data persisted by default; optional “save session” writes JSON to disk under per‑session UUID.

## Repository Layout

```
/app
  /frontend
    /src
      components/
      pages/
      state/
      utils/
    index.html
    package.json
    vite.config.ts
  /backend
    main.py
    models.py
    chem.py         # all equations and constants
    peaks.py        # smoothing + peak logic
    io_csv.py
    schemas.py
    tests/
      test_chem.py
      test_peaks.py
  /deploy
    docker-compose.yml
    nginx.conf
    certbot/
  /examples
    sample_fe.csv
    session_example.json
LICENSE
README.md
SPEC.md
```

## Config

* `.env`:

  * `APP_ENV=prod`
  * `MAX_UPLOAD_MB=10`
  * `ORIGIN=https://miareczkowanie.simon-lab.org`
* Defaults stored in `chem.py` and overridable via UI.

## Testing and CI

* pytest with numeric tolerances.
* Golden files for sample CSV.
* GitHub Actions: lint (black, isort, flake8), type check (mypy), tests, Docker build, optional deploy.

## Roadmap

* Variable-temperature `K_w(T)` and activity correction (ionic strength).
* Multi-acid baseline (e.g., HF, HCl) as options.
* Manual integration tools for overlapping peaks.
* User accounts and project storage.
* Multi-language UI (PL/EN).

## License

MIT.

## Acceptance Criteria

* Imports provided CSVs with decimal commas.
* Correct model overlay for pure H₂SO₄ when metals absent.
* ΔB step equals known spike within ±3% on synthetic tests.
* Detects Fe peak and reports concentration before pH 6.5.
* HTTPS served at the specified subdomain.

---

**Conclusion:** Scope, equations, API, UI, deployment, and acceptance criteria are defined. Use this SPEC.md to initialize the repo and start implementation.
