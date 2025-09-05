import { useEffect, useState } from 'react'
import './App.css'
import { getHealth, uploadCsv, compute } from './api/client'
import type {
  ImportResponse,
  ColumnMapping,
  ComputeResponse,
  ComputeSettings,
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
  })
  const [computing, setComputing] = useState(false)
  const [result, setResult] = useState<ComputeResponse | null>(null)

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
      {/* Upload CSV */}
      {/* ------------------------------------------------------------------ */}
      <section>
        <h2>1. Upload CSV</h2>
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
          <p style={{ marginTop: 8 }}>
            Columns detected: {importData.columns.join(', ')} ({importData.rows.length} rows)
          </p>
        )}
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Mapping */}
      {/* ------------------------------------------------------------------ */}
      {importData && mapping && (
        <section>
          <h2>2. Map Columns</h2>
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
      {/* Settings */}
      {/* ------------------------------------------------------------------ */}
      {importData && mapping && (
        <section>
          <h2>3. Settings</h2>
          {(['c_b', 'q', 'v0', 'ph_cutoff'] as const).map((k) => (
            <label key={k} style={{ marginRight: 12 }}>
              {k}:{' '}
              <input
                type="number"
                step="any"
                value={settings[k]}
                onChange={(e) => setSettings({ ...settings, [k]: parseFloat(e.target.value) })}
                style={{ width: 80 }}
              />
            </label>
          ))}
          <div style={{ marginTop: 12 }}>
            <button
              disabled={computing}
              onClick={async () => {
                if (!importData || !mapping) return
                setComputing(true)
                try {
                  const payload: ComputeSettings = {
                    ...settings,
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
              {computing ? 'Computing…' : 'Run Compute'}
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
          <h3>Plots</h3>
          <Plot
            style={{ width: '100%', height: 400 }}
            data={[
              {
                x: result.processed_table.map((r) => r.ph),
                y: result.processed_table.map((r) => r.delta_b),
                type: 'scatter',
                mode: 'lines',
                name: 'ΔB',
              },
            ]}
            layout={{ title: 'ΔB vs pH', xaxis: { title: 'pH' }, yaxis: { title: 'ΔB (mol/L)' } }}
            useResizeHandler
          />
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
        </section>
      )}
    </main>
  )
}

export default App
