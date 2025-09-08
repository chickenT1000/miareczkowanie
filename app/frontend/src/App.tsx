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
  })
  const [computing, setComputing] = useState(false)
  const [result, setResult] = useState<ComputeResponse | null>(null)
  const [showPhAlignedDeltaB, setShowPhAlignedDeltaB] = useState(true)
  // Peak assignment state
  const [peakAssignments, setPeakAssignments] = useState<Record<number, Metal | ''>>({})
  const [assigningPeaks, setAssigningPeaks] = useState(false)
  
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

  // Reset peak assignments when result changes
  useEffect(() => {
    if (result) {
      setPeakAssignments({})
    }
  }, [result])

  return (
    <main className="container" style={{ textAlign: 'left', maxWidth: 960, margin: '0 auto' }}>
      {/* ------------------------------------------------------------------ */}
      {/* Health Banner */}
      {/* ------------------------------------------------------------------ */}
      <section style={{ background: '#f4f4f4', padding: '0.5rem 1rem', marginBottom: '1rem' }}>
        {health.status === 'loading' && <span>Checking backend…</span>}
        {health.status === 'error' && <span style={{ color: 'red' }}>Backend error: {health.message}</span>}
        {health.status === 'ok' && <span style={{ color: 'green' }}>Backend OK</span>}
      </section>

      <h1>Miareczkowanie</h1>

      {/* ------------------------------------------------------------------ */}
      {/* Info / Method description */}
      {/* ------------------------------------------------------------------ */}
      <section
        style={{
          background: '#eef7ff',
          padding: '0.75rem 1rem',
          border: '1px solid #c9e2ff',
          marginBottom: '1rem',
          fontSize: 14,
        }}
      >
        <strong>What is calculated?</strong>
        <ul style={{ marginTop: 4, marginBottom: 4 }}>
          <li>H⁺ from pH, then OH⁻ via K<sub>w</sub></li>
          <li>Sulfate charge fraction&nbsp;f(H) = (H + 2·K<sub>a2</sub>)/(H + K<sub>a2</sub>)</li>
          <li>Delivered base → Na⁺ with dilution → B<sub>meas</sub></li>
          <li>Electroneutrality model gives B<sub>model</sub>; ΔB = B<sub>meas</sub> − B<sub>model</sub></li>
          <li>Cumulative derivative dΔB/dpH shows equivalence-point steps</li>
          <li>C<sub>A</sub> (total sulfate) is estimated from the initial baseline window</li>
        </ul>
        <details>
          <summary style={{ cursor: 'pointer' }}>Full description&nbsp;(click to expand)</summary>
          <p style={{ marginTop: 6 }}>
            A flowing titration with NaOH is modelled assuming only&nbsp;H₂SO₄ in the sample.
            Sodium added by the pump is corrected for dilution. Using electroneutrality,
            Na<sub>model</sub> = C<sub>A</sub>·f(H) + OH⁻ − H⁺. This is converted back to the
            normalised base axis B<sub>model</sub>. The difference ΔB highlights neutralisation
            events; its derivative pinpoints step transitions whose heights correspond to
            sulfate fractions. A robust median of baseline points estimates C<sub>A</sub>.
          </p>
        </details>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Upload CSV */}
      {/* ------------------------------------------------------------------ */}
      <section>
        <h2>1. Upload CSV</h2>
        <p style={{ fontSize: 14 }}>
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
      {/* Mapping */}
      {/* ------------------------------------------------------------------ */}
      {importData && mapping && (
        <section>
          <h2>2. Map Columns</h2>
          <p style={{ fontSize: 14, marginTop: 0 }}>
            Choose numeric pH and time columns (prefer &ldquo;time&rdquo; over
            &ldquo;time_label&rdquo;).
          </p>
          <label>
            pH column:&nbsp;
            <select
              value={mapping.ph}
              onChange={(e) => setMapping({ ...mapping, ph: e.target.value })}
            >
              {importData.columns.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          &nbsp;&nbsp;
          <label>
            Time column:&nbsp;
            <select
              value={mapping.time}
              onChange={(e) => setMapping({ ...mapping, time: e.target.value })}
            >
              {importData.columns.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
        </section>
      )}

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
              title: 'pH vs time',
              xaxis: { title: `time (${importData?.time_unit})` },
              yaxis: { title: 'pH' },
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
          <p style={{ fontSize: 14, marginTop: 0, marginBottom: 8 }}>
            Configure pump / solution parameters (used in model calculations).
          </p>
          <label style={{ marginRight: 12 }}>
            C<sub>b</sub> (NaOH conc., mol/L):{' '}
            <input
              type="number"
              step="any"
              value={settings.c_b}
              onChange={(e) => setSettings({ ...settings, c_b: parseFloat(e.target.value) })}
              style={{ width: 80 }}
            />
          </label>
          <label style={{ marginRight: 12 }}>
            q (pump flow, mL/min):{' '}
            <input
              type="number"
              step="any"
              value={settings.q}
              onChange={(e) => setSettings({ ...settings, q: parseFloat(e.target.value) })}
              style={{ width: 80 }}
            />
          </label>
          <label style={{ marginRight: 12 }}>
            V<sub>0</sub> (initial volume, mL):{' '}
            <input
              type="number"
              step="any"
              value={settings.v0}
              onChange={(e) => setSettings({ ...settings, v0: parseFloat(e.target.value) })}
              style={{ width: 80 }}
            />
          </label>
          <label style={{ marginRight: 12 }}>
            pH cutoff (peak detection):{' '}
            <input
              type="number"
              step="any"
              value={settings.ph_cutoff}
              onChange={(e) => setSettings({ ...settings, ph_cutoff: parseFloat(e.target.value) })}
              style={{ width: 80 }}
            />
          </label>
          
          <div style={{ marginTop: 12 }}>
            <label style={{ marginRight: 12, display: 'inline-flex', alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={settings.use_c_a_known}
                onChange={(e) => setSettings({ ...settings, use_c_a_known: e.target.checked })}
                style={{ marginRight: 4 }}
              />
              Use known C<sub>A</sub> (mol/L):{' '}
            </label>
            <input
              type="number"
              step="any"
              value={settings.c_a_known}
              onChange={(e) => setSettings({ ...settings, c_a_known: parseFloat(e.target.value) })}
              style={{ width: 80, marginRight: 12 }}
              disabled={!settings.use_c_a_known}
            />
            
            <label style={{ marginRight: 12 }}>
              Ignore pH below (for baseline C<sub>A</sub> estimation):{' '}
              <input
                type="number"
                step="any"
                value={settings.ph_ignore_below}
                onChange={(e) => {
                  const val = e.target.value === '' ? '' : parseFloat(e.target.value);
                  setSettings({ ...settings, ph_ignore_below: val as any });
                }}
                style={{ width: 80 }}
                placeholder="Optional"
              />
            </label>
          </div>
          
          <div style={{ marginTop: 12 }}>
            <label style={{ marginRight: 12, display: 'inline-flex', alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={settings.show_ph_aligned}
                onChange={(e) => setSettings({ ...settings, show_ph_aligned: e.target.checked })}
                style={{ marginRight: 4 }}
              />
              Show pH-aligned model overlay
            </label>
          </div>
          
          <div style={{ marginTop: 12 }}>
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
            ]}
            layout={{
              title: 'Titration Curve: pH vs Base Amount',
              xaxis: { title: 'Base amount (mol/L)' },
              yaxis: { title: 'pH' },
            }}
            useResizeHandler
          />
          <p style={{ fontSize: 13, marginTop: 4 }}>
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
                  checked={showPhAlignedDeltaB && settings.show_ph_aligned}
                  onChange={(e) => setShowPhAlignedDeltaB(e.target.checked)}
                  disabled={!settings.show_ph_aligned}
                  style={{ marginRight: 4 }}
                />
                Use pH-aligned ΔB
              </label>
            )}
          </div>
          <Plot
            style={{ width: '100%', height: 400 }}
            data={[
              {
                x: result.processed_table.map((r) => r.ph),
                y: showPhAlignedDeltaB && settings.show_ph_aligned && result.model_data.delta_b_ph_aligned
                  ? result.model_data.delta_b_ph_aligned.filter((v): v is number => v !== null)
                  : result.processed_table.map((r) => r.delta_b),
                type: 'scatter',
                mode: 'lines',
                name: showPhAlignedDeltaB && settings.show_ph_aligned ? 'ΔB (pH-aligned)' : 'ΔB',
              },
            ]}
            layout={{ 
              title: showPhAlignedDeltaB && settings.show_ph_aligned ? 'ΔB (pH-aligned) vs pH' : 'ΔB vs pH',
              xaxis: { title: 'pH' }, 
              yaxis: { title: 'ΔB (mol/L)' } 
            }}
            useResizeHandler
          />
          <p style={{ fontSize: 13, marginTop: 4 }}>
            ΔB is the difference between measured and modelled base dosage – it highlights
            deviations due to neutralisation. {showPhAlignedDeltaB && settings.show_ph_aligned && 
            'pH-aligned ΔB compares at the same pH rather than same base amount, reducing artifacts near vertical regions.'}
          </p>
          <Plot
            style={{ width: '100%', height: 400 }}
            data={[
              {
                x: result.processed_table.map((r) => r.ph),
                y: result.processed_table.map((r) => r.d_delta_b_d_ph),
                type: 'scatter',
                mode: 'lines',
                name: 'dΔB/dpH',
              },
            ]}
            layout={{
              title: 'dΔB/dpH vs pH',
              xaxis: { title: 'pH' },
              yaxis: { title: 'dΔB/dpH' },
            }}
            useResizeHandler
          />
          <p style={{ fontSize: 13, marginTop: 4 }}>
            The derivative dΔB/dpH accentuates step transitions corresponding to equivalence
            points.
          </p>

          {/* -------------------------------------------------------------- */}
          {/* Detected Peaks and Metal Assignment                           */}
          {/* -------------------------------------------------------------- */}
          {result.peaks.length > 0 && (
            <>
              <h3>Detected Peaks</h3>
              <p style={{ fontSize: 13, marginTop: 4, marginBottom: 8 }}>
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

          <h3>Processed Table (first 100 rows)</h3>
          <div style={{ overflowX: 'auto' }}>
            <table border={1} cellPadding={4} style={{ borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr>
                  {Object.keys(result.processed_table[0]).map((col) => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.processed_table.slice(0, 100).map((row, idx) => (
                  <tr key={idx}>
                    {Object.values(row).map((v, i) => (
                      <td key={i}>{typeof v === 'number' ? v.toFixed(4) : v}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* -------------------------------------------------------------- */}
          {/* Export buttons                                                */}
          {/* -------------------------------------------------------------- */}
          <h3>Export</h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              onClick={async () => {
                const res = await exportData('csv', 'processed')
                downloadFile(res.filename, res.content_type, res.data)
              }}
            >
              Processed CSV
            </button>
            <button
              onClick={async () => {
                const res = await exportData('json', 'processed')
                downloadFile(res.filename, res.content_type, res.data)
              }}
            >
              Processed JSON
            </button>
            <button
              onClick={async () => {
                const res = await exportData('json', 'peaks')
                downloadFile(res.filename, res.content_type, res.data)
              }}
            >
              Peaks JSON
            </button>
            <button
              onClick={async () => {
                const res = await exportData('json', 'session')
                downloadFile(res.filename, res.content_type, res.data)
              }}
            >
              Session JSON
            </button>
          </div>
        </section>
      )}
    </main>
  )
}

export default App
