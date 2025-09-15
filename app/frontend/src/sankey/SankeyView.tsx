import { useEffect, useState, useRef } from 'react'
import type { ChangeEvent } from 'react'
import type { Graph } from '../api/sankey'
import { getGraph, scaleGraph, importData, downloadGraph } from '../api/sankey'

// Plotly --------------------------------------------------------------------
import createPlotlyComponent from 'react-plotly.js/factory'
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore – plotly.js-dist-min has no types, but we ship @types/plotly.js for API
import Plotly from 'plotly.js-dist-min'
const Plot = createPlotlyComponent(Plotly)

interface SankeyViewProps {
  onBack?: () => void;
}

export default function SankeyView({ onBack }: SankeyViewProps) {
  const [graph, setGraph] = useState<Graph | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [batchTarget, setBatchTarget] = useState(300)
  const [useScaled, setUseScaled] = useState(false)
  const [scaling, setScaling] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Load graph on mount
  useEffect(() => {
    let mounted = true
    
    const fetchGraph = async () => {
      try {
        setLoading(true)
        const data = await getGraph()
        if (mounted) {
          setGraph(data)
          if (data.meta.batch_target_kg) {
            setBatchTarget(data.meta.batch_target_kg)
          }
        }
      } catch (err) {
        if (mounted) setError(`Failed to load graph: ${err instanceof Error ? err.message : String(err)}`)
      } finally {
        if (mounted) setLoading(false)
      }
    }
    
    fetchGraph()
    
    return () => {
      mounted = false
    }
  }, [])

  // Apply scaling
  const handleScale = async () => {
    if (!graph) return
    
    try {
      setScaling(true)
      const scaledGraph = await scaleGraph(batchTarget, "global")
      setGraph(scaledGraph)
      setUseScaled(true)
    } catch (err) {
      setError(`Scaling failed: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setScaling(false)
    }
  }

  // Handle file import
  const handleImport = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    try {
      const fileContent = await file.text()
      const fileType = file.name.toLowerCase().endsWith('.csv') ? 'csv' : 'json'
      
      const importedGraph = await importData(fileContent, fileType as any)
      setGraph(importedGraph)
      
      if (importedGraph.meta.batch_target_kg) {
        setBatchTarget(importedGraph.meta.batch_target_kg)
      }
      
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    } catch (err) {
      setError(`Import failed: ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  // Handle export
  const handleExport = () => {
    if (!graph) return
    downloadGraph(graph, `sankey_graph_${new Date().toISOString().slice(0, 10)}.json`)
  }

  // Prepare Sankey data
  const prepareSankeyData = () => {
    if (!graph) return null
    
    // Map node IDs to indices for Plotly
    const nodeMap: Record<string, number> = {}
    graph.nodes.forEach((node, index) => {
      nodeMap[node.id] = index
    })
    
    // Prepare arrays for Plotly Sankey
    const source: number[] = []
    const target: number[] = []
    const value: number[] = []
    const labels: string[] = graph.nodes.map(n => n.label)
    
    // Color nodes by type
    const colors: string[] = graph.nodes.map(node => {
      switch (node.type) {
        case 'machine': return '#e41a1c'  // Red
        case 'stream': return '#377eb8'   // Blue
        case 'product': return '#4daf4a'  // Green
        default: return '#999999'         // Gray
      }
    })
    
    // Prepare links
    graph.links.forEach(link => {
      const sourceIndex = nodeMap[link.from]
      const targetIndex = nodeMap[link.to]
      
      // Use scaled values if available and selected
      const linkValue = useScaled && link.scaled_kg != null 
        ? link.scaled_kg 
        : link.measured_kg
      
      // Only add links with values
      if (linkValue != null && linkValue > 0) {
        source.push(sourceIndex)
        target.push(targetIndex)
        value.push(linkValue)
      }
    })
    
    return {
      source,
      target,
      value,
      labels,
      colors
    }
  }

  const sankeyData = prepareSankeyData()

  return (
    <main style={{ textAlign: 'left', width: '95%', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h1>Sankey Diagram</h1>
        {onBack && (
          <button onClick={onBack} style={{ padding: '0.5rem 1rem' }}>
            Back to Titration
          </button>
        )}
      </div>
      
      {error && (
        <div style={{ background: '#ffeeee', padding: '0.5rem 1rem', marginBottom: '1rem', color: 'red' }}>
          {error}
          <button 
            onClick={() => setError(null)} 
            style={{ marginLeft: '1rem', border: 'none', background: 'transparent', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>
      )}
      
      <div style={{ background: '#f4f4f4', padding: '1rem', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center' }}>
          <div>
            <label>
              Batch Target (kg):&nbsp;
              <input
                type="number"
                value={batchTarget}
                onChange={e => setBatchTarget(Number(e.target.value))}
                style={{ width: '80px' }}
                min="1"
              />
            </label>
            <button 
              onClick={handleScale} 
              disabled={scaling || !graph}
              style={{ marginLeft: '0.5rem' }}
            >
              {scaling ? 'Scaling...' : 'Apply Scaling'}
            </button>
          </div>
          
          <label style={{ display: 'flex', alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={useScaled}
              onChange={e => setUseScaled(e.target.checked)}
              disabled={!graph?.links.some(l => l.scaled_kg != null)}
              style={{ marginRight: '0.5rem' }}
            />
            Show Scaled Values
          </label>
          
          <div>
            <input
              type="file"
              accept=".json,.csv"
              onChange={handleImport}
              ref={fileInputRef}
              style={{ display: 'none' }}
            />
            <button onClick={() => fileInputRef.current?.click()}>
              Import JSON/CSV
            </button>
            <button 
              onClick={handleExport} 
              disabled={!graph}
              style={{ marginLeft: '0.5rem' }}
            >
              Export JSON
            </button>
          </div>
        </div>
      </div>
      
      {loading ? (
        <div style={{ textAlign: 'center', padding: '2rem' }}>Loading Sankey data...</div>
      ) : !graph ? (
        <div style={{ textAlign: 'center', padding: '2rem' }}>No graph data available</div>
      ) : sankeyData && sankeyData.source.length > 0 ? (
        <Plot
          style={{ width: '100%', height: '700px' }}
          data={[
            {
              type: 'sankey',
              orientation: 'h',
              node: {
                pad: 15,
                thickness: 20,
                line: {
                  color: 'black',
                  width: 0.5
                },
                label: sankeyData.labels,
                color: sankeyData.colors
              },
              link: {
                source: sankeyData.source,
                target: sankeyData.target,
                value: sankeyData.value,
                hovertemplate: 
                  '%{source.label} → %{target.label}<br>' +
                  'Value: %{value:.2f} kg<br>' +
                  '<extra></extra>'
              }
            }
          ]}
          layout={{
            title: `Process Flow Sankey Diagram (${useScaled ? 'Scaled' : 'Measured'} Values)`,
            font: {
              size: 12
            },
            autosize: true,
            margin: {
              l: 25,
              r: 25,
              b: 25,
              t: 50,
              pad: 4
            }
          }}
          useResizeHandler
        />
      ) : (
        <div style={{ textAlign: 'center', padding: '2rem' }}>
          Graph loaded but no valid links with values found
        </div>
      )}
      
      {graph && (
        <div style={{ marginTop: '1rem', fontSize: '14px' }}>
          <p>
            <strong>Graph Info:</strong> {graph.meta.notes || 'No notes provided'}
          </p>
          <p>
            <strong>Nodes:</strong> {graph.nodes.length} | 
            <strong> Links:</strong> {graph.links.length} | 
            <strong> Sources:</strong> {graph.sources.join(', ')} | 
            <strong> Sinks:</strong> {graph.sinks.length} items
          </p>
        </div>
      )}
    </main>
  )
}
