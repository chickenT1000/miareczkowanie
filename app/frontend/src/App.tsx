import { useEffect, useState } from 'react'
import './App.css'
import { getHealth, uploadCsv, compute, exportData, assignPeaks } from './api/client'
import type {
  ImportResponse,
  ColumnMapping,
  ComputeResponse,
  ComputeSettings,
  Metal,
  PeakAssignment,
} from './api/client'

// Plotly --------------------------------------------------------------------
import createPlotlyComponent from 'react-plotly.js/factory'
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore – plotly.js-dist-min has no types, but we ship @types/plotly.js for API
import Plotly from 'plotly.js-dist-min'
const Plot = createPlotlyComponent(Plotly)

type HealthState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ok'; payload: unknown }

function App() {
  const [health, setHealth] = useState<HealthState>({ status: 'loading' })
  const [uploading, setUploading] = useState(false)
  const [importData, setImportData] = useState<ImportResponse | null>(null)
  const [mapping, setMapping] = useState<ColumnMapping | null>(null)
  const [settings, setSettings] = useState({
    c_b: 0.1,
    q: 1.0,
    v0: 100,
    t: 25,
    ph_cutoff: 6.5,
    c_a_known: 0.2,
    use_c_a_known: false,
    ph_ignore_below: 1.0,
    show_ph_aligned: false,
    use_contact_point: true,
    contact_ph_min: 1.0,
  })
  const [computing, setComputing] = useState(false)
  const [result, setResult] = useState<ComputeResponse | null>(null)
  const [showPhAlignedDeltaB, setShowPhAlignedDeltaB] = useState(true)
  // Peak assignment state
  const [peakAssignments, setPeakAssignments] = useState<Record<number, Metal | ''>>({})
  const [assigningPeaks, setAssigningPeaks] = useState(false)
  // Dark mode detection
  const [prefersDark, setPrefersDark] = useState(false)
  
  // Preview arrays for pH-time plot
  const previewPh: number[] =
    importData && mapping
      ? (importData.rows
          .map((r) => Number(r[mapping.ph]))
          .filter((v) => !Number.isNaN(v)) as number[])
      : []
  const previewTime: number[] =
    importData && mapping
      ? (importData.rows
          .map((r) => Number(r[mapping.time]))
          .filter((v) => !Number.isNaN(v)) as number[])
      : []

  // Base plot layout for dark mode compatibility
  const plotLayoutBase = {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: {
      color: prefersDark ? '#e5e7eb' : '#111827',
    },
    xaxis: {
      gridcolor: prefersDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
    },
    yaxis: {
      gridcolor: prefersDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
    },
  }

  /* ---------------------------------------------------------------------- */
  /* Helper: trigger client-side download                                   */
  /* ---------------------------------------------------------------------- */
  const downloadFile = (filename: string, contentType: string, data: any) => {
    const blob =
      typeof data === 'string'
        ? new Blob([data], { type: contentType })
        : new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  /* ---------------------------------------------------------------------- */
  /* Helper: calculate finite difference derivative                         */
  /* ---------------------------------------------------------------------- */
  const calculateDerivative = (x: number[], y: number[]): number[] => {
    if (x.length !== y.length || x.length < 2) {
      return Array(y.length).fill(0);
    }
    
    const derivative: number[] = [];
    
    // First point - forward difference
    derivative.push((y[1] - y[0]) / (x[1] - x[0]));
    
    // Middle points - central difference
    for (let i = 1; i < x.length - 1; i++) {
      derivative.push((y[i + 1] - y[i - 1]) / (x[i + 1] - x[i - 1]));
    }
    
    // Last point - backward difference
    derivative.push((y[y.length - 1] - y[y.length - 2]) / (x[x.length - 1] - x[x.length - 2]));
    
    return derivative;
  }

  useEffect(() => {
    let mounted = true
    getHealth()
      .then((data) => {
        if (mounted) setHealth({ status: 'ok', payload: data })
      })
      .catch((err: unknown) => {
        if (mounted)
          setHealth({
            status: 'error',
            message:
              err instanceof Error ? err.message : 'Unknown error contacting backend',
          })
      })
    return () => {
      mounted = false
    }
  }, [])

  // Detect dark mode preference
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = (e: MediaQueryListEvent) => {
      setPrefersDark(e.matches)
    }
    
    // Set initial value
    setPrefersDark(mediaQuery.matches)
    
    // Add listener for changes
    mediaQuery.addEventListener('change', handleChange)
    
    // Cleanup
    return () => {
      mediaQuery.removeEventListener('change', handleChange)
    }
  }, [])

  // Reset peak assignments when result changes
  useEffect(() => {
    if (result) {
      setPeakAssignments({})
    }
  }, [result])

  return (
    <main className="container">
      {/* ------------------------------------------------------------------ */}
      {/* Health Banner */}
      {/* ------------------------------------------------------------------ */}
      <section className="cardish">
        {health.status === 'loading' && <span>Checking backend…</span>}
        {health.status === 'error' && <span style={{ color: 'red' }}>Backend error: {health.message}</span>}
        {health.status === 'ok' && <span style={{ color: 'green' }}>Backend OK</span>}
      </section>

      <h1>Miareczkowanie</h1>

      {/* ------------------------------------------------------------------ */}
      {/* Info / Method description */}
      {/* ------------------------------------------------------------------ */}
      <section className="cardish">
        <strong>What is calculated?</strong>
        <p className="setting-description">
          A flowing titration with NaOH is modelled assuming only&nbsp;H₂SO₄ in the sample.
          Sodium added by the pump is corrected for dilution. Using electroneutrality,
          Na<sub>model</sub> = C<sub>A</sub>·f(H) + OH⁻ − H⁺. This is converted back to the
          normalised base axis B<sub>model</sub>. The difference ΔB highlights neutralisation
          events; its derivative pinpoints step transitions whose heights correspond to
          sulfate fractions. A robust median of baseline points estimates C<sub>A</sub>.
        </p>
        <ul style={{ marginTop: 4, marginBottom: 4, fontSize: 16 }}>
          <li>H⁺ from pH, then OH⁻ via K<sub>w</sub></li>
          <li>Sulfate charge fraction&nbsp;f(H) = (H + 2·K<sub>a2</sub>)/(H + K<sub>a2</sub>)</li>
          <li>Delivered base → Na⁺ with dilution → B<sub>meas</sub></li>
          <li>Electroneutrality model gives B<sub>model</sub>; ΔB = B<sub>meas</sub> − B<sub>model</sub></li>
          <li>Cumulative derivative dΔB/dpH shows equivalence-point steps</li>
          <li>C<sub>A</sub> (total sulfate) is estimated from the initial baseline window</li>
        </ul>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Upload CSV */}
      {/* ------------------------------------------------------------------ */}
      <section>
        <h2>1. Upload CSV</h2>
        <p className="setting-description">
          Supported: instrument export or any CSV with pH and time columns. Decimal&nbsp;comma and
          semicolon separators are detected automatically.
        </p>
        <input
          type="file"
          accept=".csv,.txt"
          disabled={uploading}
          onChange={async (e) => {
            const file = e.target.files?.[0]
            if (!file) return
            setUploading(true)
            try {
              const data = await uploadCsv(file)
              setImportData(data)
              // auto mapping heuristics
              const phCol =
                data.columns.find((c) => c.toLowerCase().includes('ph')) ?? data.columns[0]
              const timeCol =
                data.columns.find((c) => c.toLowerCase().includes('time') || c.toLowerCase().includes('czas')) ??
                data.columns[1] ??
                data.columns[0]
              setMapping({ ph: phCol, time: timeCol })
              setResult(null)
            } catch (err) {
              alert(`Import failed: ${err}`)
            } finally {
              setUploading(false)
            }
          }}
        />
        {importData && (
          <p style={{ marginTop: 8, fontSize: 14 }}>
            Columns&nbsp;detected: {importData.columns.join(', ')} · rows:{' '}
            {importData.rows.length} · separator: "{importData.column_separator}" · decimal "
            {importData.decimal_separator}" · time unit: {importData.time_unit}
          </p>
        )}
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Preview plot pH vs time                                            */}
      {/* ------------------------------------------------------------------ */}
      {previewPh.length > 2 && (
        <section style={{ marginTop: 16 }}>
          <h3>Preview: pH vs time</h3>
          <Plot
            style={{ width: '100%', height: 300 }}
            data={[
              {
                x: previewTime,
                y: previewPh,
                type: 'scatter',
                mode: 'lines',
                name: 'pH',
              },
            ]}
            layout={{
              ...plotLayoutBase,
              title: 'pH vs time',
              xaxis: { 
                ...plotLayoutBase.xaxis,
                title: `time (${importData?.time_unit})` 
              },
              yaxis: { 
                ...plotLayoutBase.yaxis,
                title: 'pH' 
              },
            }}
            useResizeHandler
          />
        </section>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Settings */}
      {/* ------------------------------------------------------------------ */}
      {importData && mapping && (
        <section>
          <h2>3. Settings</h2>
          <p className="setting-description">
            Configure pump / solution parameters (used in model calculations).
          </p>
          
          <div className="setting-row">
            <label title="Concentration of NaOH solution used by the pump">
              C<sub>b</sub> (NaOH concentration, mol/L):
            </label>
            <input
              type="number"
              step="any"
              value={settings.c_b}
              onChange={(e) => setSettings({ ...settings, c_b: parseFloat(e.target.value) })}
              style={{ width: 120 }}
            />
          </div>
          
          <div className="setting-row">
            <label title="Flow rate of the pump in milliliters per minute">
              q (pump flow, mL/min):
            </label>
            <input
              type="number"
              step="any"
              value={settings.q}
              onChange={(e) => setSettings({ ...settings, q: parseFloat(e.target.value) })}
              style={{ width: 120 }}
            />
          </div>
          
          <div className="setting-row">
            <label title="Initial volume of the sample before titration begins">
              V<sub>0</sub> (initial volume, mL):
            </label>
            <input
              type="number"
              step="any"
              value={settings.v0}
              onChange={(e) => setSettings({ ...settings, v0: parseFloat(e.target.value) })}
              style={{ width: 120 }}
            />
          </div>
          
          <div className="setting-row">
            <label title="pH threshold for peak detection, peaks above this value are detected">
              pH cutoff (peak detection):
            </label>
            <input
              type="number"
              step="any"
              value={settings.ph_cutoff}
              onChange={(e) => setSettings({ ...settings, ph_cutoff: parseFloat(e.target.value) })}
              style={{ width: 120 }}
            />
          </div>
          
          <div className="setting-row">
            <label style={{ display: 'flex', alignItems: 'center' }} title="Use a known acid concentration instead of estimating from baseline">
              <input
                type="checkbox"
                checked={settings.use_c_a_known}
                onChange={(e) => setSettings({ ...settings, use_c_a_known: e.target.checked })}
                style={{ marginRight: 8 }}
              />
              Use known C<sub>A</sub> (mol/L):
            </label>
            <input
              type="number"
              step="any"
              value={settings.c_a_known}
              onChange={(e) => setSettings({ ...settings, c_a_known: parseFloat(e.target.value) })}
              style={{ width: 120 }}
              disabled={!settings.use_c_a_known}
              title="Known acid concentration value in mol/L"
            />
          </div>
          
          <div className="setting-row">
            <label title="Ignore pH values below this threshold when estimating acid concentration from baseline">
              Ignore pH below (for baseline C<sub>A</sub> estimation):
            </label>
            <input
              type="number"
              step="any"
              value={settings.ph_ignore_below}
              onChange={(e) => {
                const val = e.target.value === '' ? '' : parseFloat(e.target.value);
                setSettings({ ...settings, ph_ignore_below: val as any });
              }}
              style={{ width: 120 }}
              placeholder="Optional"
              title="Only applies when C_A is not provided"
            />
          </div>
          
          <div className="setting-row">
            <label style={{ display: 'flex', alignItems: 'center' }} title="Align model to match measured curve at first point with pH ≥ contact_ph_min">
              <input
                type="checkbox"
                checked={settings.use_contact_point}
                onChange={(e) => setSettings({ ...settings, use_contact_point: e.target.checked })}
                style={{ marginRight: 8 }}
                disabled={settings.use_c_a_known}
              />
              Use contact point (when C<sub>A</sub> unknown)
            </label>
          </div>
          
          <div className="setting-row">
            <label title="Minimum pH threshold for selecting contact point">
              Contact pH min:
            </label>
            <input
              type="number"
              step="any"
              value={settings.contact_ph_min}
              onChange={(e) => setSettings({ ...settings, contact_ph_min: parseFloat(e.target.value) })}
              style={{ width: 120 }}
              disabled={settings.use_c_a_known || !settings.use_contact_point}
            />
          </div>
          
          <div className="setting-row">
            <label style={{ display: 'flex', alignItems: 'center' }} title="Show pH-aligned model overlay in titration curve">
              <input
                type="checkbox"
                checked={settings.show_ph_aligned}
                onChange={(e) => setSettings({ ...settings, show_ph_aligned: e.target.checked })}
                style={{ marginRight: 8 }}
              />
              Show pH-aligned model overlay
            </label>
          </div>
          
          <div style={{ marginTop: 20 }}>
            <button
              disabled={computing}
              onClick={async () => {
                if (!importData || !mapping) return
                setComputing(true)
                try {
                  const payload: ComputeSettings = {
                    ...settings,
                    c_a_known: settings.use_c_a_known ? settings.c_a_known : null,
                    ph_ignore_below: settings.ph_ignore_below || null,
                    use_contact_point: settings.use_contact_point,
                    contact_ph_min: settings.contact_ph_min,
                    start_index: 0,
                    column_mapping: mapping,
                    rows: importData.rows,
                  }
                  const res = await compute(payload)
                  setResult(res)
                } catch (err) {
                  alert(`Compute failed: ${err}`)
                } finally {
                  setComputing(false)
                }
              }}
            >
              {computing ? 'Computing…' : 'Compute results'}
            </button>
          </div>
        </section>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Results */}
      {/* ------------------------------------------------------------------ */}
      {result && (
        <section>
          <h2>4. Results</h2>
          <p style={{ fontSize: 16, fontWeight: 500 }}>
            {settings.use_c_a_known ? 'Using known' : 'Estimated'} C<sub>A</sub>: {result.c_a.toFixed(4)} mol/L
          </p>
          <h3>Measured vs Model Base</h3>
          <Plot
            style={{ width: '100%', height: 400 }}
            data={[
              {
                x: result.processed_table.map((r) => r.b_meas),
                y: result.processed_table.map((r) => r.ph),
                type: 'scatter',
                mode: 'lines',
                name: 'Measured (B_meas)',
              },
              (() => {
                // Prefer standalone curve if provided by backend
                const hasStandalone =
                  result.model_data.ph_model &&
                  result.model_data.b_model_curve &&
                  result.model_data.ph_model.length ===
                    result.model_data.b_model_curve.length &&
                  result.model_data.ph_model.length > 0

                if (hasStandalone) {
                  return {
                    x: result.model_data.b_model_curve as number[],
                    y: result.model_data.ph_model as number[],
                    type: 'scatter',
                    mode: 'lines',
                    name: 'Model (standalone)',
                    line: { dash: 'dash' },
                  }
                }

                // Legacy fallback: use B_model aligned to measured pH
                const maxBMeas = Math.max(
                  ...result.processed_table.map((r) => r.b_meas),
                )
                const threshold = 5 * maxBMeas
                return {
                  x: result.model_data.b_model.map((v) =>
                    Math.abs(v) > threshold ? null : v,
                  ),
                  y: result.model_data.ph,
                  type: 'scatter',
                  mode: 'lines',
                  name: 'Model (B_model)',
                  line: { dash: 'dash' },
                }
              })(),
              ...(settings.show_ph_aligned && result.model_data.b_model_ph_aligned ? [
                {
                  x: result.model_data.b_model_ph_aligned.filter((v): v is number => v !== null),
                  y: result.model_data.ph.filter((_, i) => result.model_data.b_model_ph_aligned?.[i] !== null),
                  type: 'scatter',
                  mode: 'lines',
                  name: 'Model (pH-aligned)',
                  line: { dash: 'dashdot', color: 'rgba(255, 100, 50, 0.8)' },
                }
              ] : []),
              ...(settings.show_ph_aligned && settings.use_contact_point && 
                  result.model_data.b_model_ph_contacted ? [
                {
                  x: result.model_data.b_model_ph_contacted.filter((v): v is number => v !== null),
                  y: result.model_data.ph.filter((_, i) => result.model_data.b_model_ph_contacted?.[i] !== null),
                  type: 'scatter',
                  mode: 'lines',
                  name: 'Model (contacted)',
                  line: { dash: 'dot', color: 'rgba(50, 150, 255, 0.8)' },
                }
              ] : []),
            ]}
            layout={{
              ...plotLayoutBase,
              title: 'Titration Curve: pH vs Base Amount',
              xaxis: { 
                ...plotLayoutBase.xaxis,
                title: 'Base amount (mol/L)' 
              },
              yaxis: { 
                ...plotLayoutBase.yaxis,
                title: 'pH' 
              },
            }}
            useResizeHandler
          />
          <p className="setting-description">
            Titration curve showing pH vs normalized base amount. The measured data (solid line) is compared with 
            the theoretical H₂SO₄-only model (dashed line). Extreme model values are masked for better visualization.
          </p>
          <h3>Plots</h3>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ marginRight: 12 }}>ΔB vs pH</span>
            {result.model_data.delta_b_ph_aligned && (
              <label style={{ fontSize: 14, display: 'inline-flex', alignItems: 'center' }}>
                <input
                  type="checkbox"
                  checked={showPhAlignedDeltaB}
                  onChange={(e) => setShowPhAlignedDeltaB(e.target.checked)}
                  style={{ marginRight: 4 }}
                />
                Use pH-aligned ΔB
              </label>
            )}
          </div>
          
          {/* Prepare data for ΔB vs pH plot */}
          {(() => {
            // Get the appropriate delta_b array based on settings
            let deltaB = result.processed_table.map(r => r.delta_b);
            let phValues = result.processed_table.map(r => r.ph);
            let plotTitle = 'ΔB vs pH';
            
            if (showPhAlignedDeltaB) {
              if (settings.use_contact_point && result.model_data.delta_b_ph_contacted) {
                // Filter out nulls and get corresponding pH values
                const validIndices: number[] = [];
                const filteredDeltaB: number[] = [];
                const filteredPh: number[] = [];
                
                result.model_data.delta_b_ph_contacted.forEach((val, idx) => {
                  if (val !== null) {
                    validIndices.push(idx);
                    filteredDeltaB.push(val);
                    filteredPh.push(result.model_data.ph[idx]);
                  }
                });
                
                deltaB = filteredDeltaB;
                phValues = filteredPh;
                plotTitle = 'ΔB (contacted) vs pH';
              } 
              else if (result.model_data.delta_b_ph_aligned) {
                // Filter out nulls and get corresponding pH values
                const validIndices: number[] = [];
                const filteredDeltaB: number[] = [];
                const filteredPh: number[] = [];
                
                result.model_data.delta_b_ph_aligned.forEach((val, idx) => {
                  if (val !== null) {
                    validIndices.push(idx);
                    filteredDeltaB.push(val);
                    filteredPh.push(result.model_data.ph[idx]);
                  }
                });
                
                deltaB = filteredDeltaB;
                phValues = filteredPh;
                plotTitle = 'ΔB (pH-aligned) vs pH';
              }
            }
            
            return (
              <Plot
                style={{ width: '100%', height: 400 }}
                data={[
                  {
                    x: phValues,
                    y: deltaB,
                    type: 'scatter',
                    mode: 'lines',
                    name: showPhAlignedDeltaB ? 
                      (settings.use_contact_point && result.model_data.delta_b_ph_contacted ? 'ΔB (contacted)' : 'ΔB (pH-aligned)') : 
                      'ΔB',
                  },
                ]}
                layout={{ 
                  ...plotLayoutBase,
                  title: plotTitle,
                  xaxis: { 
                    ...plotLayoutBase.xaxis,
                    title: 'pH' 
                  }, 
                  yaxis: { 
                    ...plotLayoutBase.yaxis,
                    title: 'ΔB (mol/L)' 
                  } 
                }}
                useResizeHandler
              />
            );
          })()}
          
          <p className="setting-description">
            ΔB is the difference between measured and modelled base dosage – it highlights
            deviations due to neutralisation. {showPhAlignedDeltaB && 
            (settings.use_contact_point && result.model_data.delta_b_ph_contacted ? 
              'Contact-point anchoring aligns the model to match the measured curve at the first point with pH ≥ contact_ph_min.' :
              'pH-aligned ΔB compares at the same pH rather than same base amount, reducing artifacts near vertical regions.')}
          </p>
          
          {/* Derivative plot with on-the-fly calculation */}
          {(() => {
            // Get the appropriate delta_b array based on settings - same logic as above
            let deltaB = result.processed_table.map(r => r.delta_b);
            let phValues = result.processed_table.map(r => r.ph);
            let plotTitle = 'dΔB/dpH vs pH';
            
            if (showPhAlignedDeltaB) {
              if (settings.use_contact_point && result.model_data.delta_b_ph_contacted) {
                // Filter out nulls and get corresponding pH values
                const validIndices: number[] = [];
                const filteredDeltaB: number[] = [];
                const filteredPh: number[] = [];
                
                result.model_data.delta_b_ph_contacted.forEach((val, idx) => {
                  if (val !== null) {
                    validIndices.push(idx);
                    filteredDeltaB.push(val);
                    filteredPh.push(result.model_data.ph[idx]);
                  }
                });
                
                deltaB = filteredDeltaB;
                phValues = filteredPh;
                plotTitle = 'dΔB/dpH (contacted) vs pH';
              } 
              else if (result.model_data.delta_b_ph_aligned) {
                // Filter out nulls and get corresponding pH values
                const validIndices: number[] = [];
                const filteredDeltaB: number[] = [];
                const filteredPh: number[] = [];
                
                result.model_data.delta_b_ph_aligned.forEach((val, idx) => {
                  if (val !== null) {
                    validIndices.push(idx);
                    filteredDeltaB.push(val);
                    filteredPh.push(result.model_data.ph[idx]);
                  }
                });
                
                deltaB = filteredDeltaB;
                phValues = filteredPh;
                plotTitle = 'dΔB/dpH (pH-aligned) vs pH';
              }
            }
            
            // Calculate derivative on the fly
            const dDeltaBdPh = calculateDerivative(phValues, deltaB);
            
            return (
              <Plot
                style={{ width: '100%', height: 400 }}
                data={[
                  {
                    x: phValues,
                    y: dDeltaBdPh,
                    type: 'scatter',
                    mode: 'lines',
                    name: showPhAlignedDeltaB ? 
                      (settings.use_contact_point && result.model_data.delta_b_ph_contacted ? 'dΔB/dpH (contacted)' : 'dΔB/dpH (pH-aligned)') : 
                      'dΔB/dpH',
                  },
                ]}
                layout={{ 
                  ...plotLayoutBase,
                  title: plotTitle,
                  xaxis: { 
                    ...plotLayoutBase.xaxis,
                    title: 'pH' 
                  }, 
                  yaxis: { 
                    ...plotLayoutBase.yaxis,
                    title: 'dΔB/dpH' 
                  } 
                }}
                useResizeHandler
              />
            );
          })()}
          
          <p className="setting-description">
            The derivative dΔB/dpH accentuates step transitions corresponding to equivalence
            points. {showPhAlignedDeltaB && 'The derivative is calculated from the selected ΔB data.'}
          </p>

          {/* -------------------------------------------------------------- */}
          {/* Detected Peaks and Metal Assignment                           */}
          {/* -------------------------------------------------------------- */}
          {result.peaks.length > 0 && (
            <>
              <h3>Detected Peaks</h3>
              <p className="setting-description">
                Assign metals to detected peaks to calculate concentrations.
              </p>
              <table border={1} cellPadding={4} style={{ borderCollapse: 'collapse', fontSize: 14 }}>
                <thead>
                  <tr>
                    <th>Peak ID</th>
                    <th>pH Range</th>
                    <th>ΔB Step</th>
                    <th>Metal</th>
                    <th>Stoichiometry</th>
                    <th>Concentration (mol/L)</th>
                    <th>Concentration (mg/L)</th>
                  </tr>
                </thead>
                <tbody>
                  {result.peaks.map((peak) => (
                    <tr key={peak.peak_id}>
                      <td>{peak.peak_id}</td>
                      <td>{peak.ph_start.toFixed(2)} - {peak.ph_end.toFixed(2)}</td>
                      <td>{peak.delta_b_step.toFixed(5)}</td>
                      <td>
                        <select
                          value={peakAssignments[peak.peak_id] || peak.metal || ''}
                          onChange={(e) => {
                            const value = e.target.value as Metal | '';
                            setPeakAssignments({
                              ...peakAssignments,
                              [peak.peak_id]: value
                            });
                          }}
                        >
                          <option value="">-- Select Metal --</option>
                          <option value="Fe3+">Fe³⁺</option>
                          <option value="Ni2+">Ni²⁺</option>
                          <option value="Co2+">Co²⁺</option>
                          <option value="Fe2+">Fe²⁺</option>
                          <option value="Al3+">Al³⁺</option>
                          <option value="Mn2+">Mn²⁺</option>
                        </select>
                      </td>
                      <td>{peak.stoichiometry || '-'}</td>
                      <td>{peak.c_metal ? peak.c_metal.toFixed(5) : '-'}</td>
                      <td>{peak.mg_l ? peak.mg_l.toFixed(2) : '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ marginTop: 12 }}>
                <button
                  disabled={assigningPeaks || Object.keys(peakAssignments).length === 0}
                  onClick={async () => {
                    // Filter out empty assignments
                    const assignments: PeakAssignment[] = Object.entries(peakAssignments)
                      .filter(([, metal]) => metal !== '')
                      .map(([peakId, metal]) => ({
                        peak_id: parseInt(peakId),
                        metal: metal as Metal
                      }));
                    
                    if (assignments.length === 0) return;
                    
                    setAssigningPeaks(true);
                    try {
                      const updatedPeaks = await assignPeaks(assignments);
                      // Update result with new peaks
                      setResult({
                        ...result,
                        peaks: updatedPeaks
                      });
                      // Clear assignments since they're now applied
                      setPeakAssignments({});
                    } catch (err) {
                      alert(`Assignment failed: ${err}`);
                    } finally {
                      setAssigningPeaks(false);
                    }
                  }}
                >
                  {assigningPeaks ? 'Assigning...' : 'Assign & Quantify'}
                </button>
              </div>

              {/* Totals summary for selected metals */}
              {(() => {
                const metalsToSum: Metal[] = ['Fe3+', 'Ni2+', 'Co2+']
                const totals = metalsToSum.map((m) => {
                  const rows = result.peaks.filter(
                    (p) => p.metal === m && p.c_metal != null && p.mg_l != null,
                  )
                  return {
                    metal: m,
                    c: rows.reduce((acc, p) => acc + (p.c_metal || 0), 0),
                    mg: rows.reduce((acc, p) => acc + (p.mg_l || 0), 0),
                  }
                })
                const anyAssigned = totals.some((t) => t.c > 0)
                if (!anyAssigned) return null
                return (
                  <div style={{ marginTop: 12, fontSize: 14 }}>
                    <strong>Totals:</strong>
                    <ul style={{ margin: '4px 0 0 16px' }}>
                      {totals.map((t) => (
                        <li key={t.metal}>
                          {t.metal}: {t.c.toFixed(5)} mol/L &nbsp;|&nbsp;{' '}
                          {t.mg.toFixed(2)} mg/L
                        </li>
                      ))}
                    </ul>
                  </div>
                )
              })()}
            </>
          )}

          {/* -------------------------------------------------------------- */}
          {/* Single JSON export                                            */}
          {/* -------------------------------------------------------------- */}
          <h3>Export</h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              onClick={async () => {
                const res = await exportData('json', 'session')
                downloadFile(res.filename, res.content_type, res.data)
              }}
            >
              Export all (JSON)
            </button>
          </div>
        </section>
      )}
    </main>
  )
}

export default App
