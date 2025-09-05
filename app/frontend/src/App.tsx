import { useEffect, useState } from 'react'
import './App.css'
import { getHealth } from './api/client'

type HealthState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ok'; payload: unknown }

function App() {
  const [health, setHealth] = useState<HealthState>({ status: 'loading' })

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
    <main className="container">
      <h1>Miareczkowanie – Backend Health</h1>
      {health.status === 'loading' && <p>Checking backend…</p>}
      {health.status === 'error' && (
        <p style={{ color: 'red' }}>Error: {health.message}</p>
      )}
      {health.status === 'ok' && (
        <>
          <p style={{ color: 'green' }}>Backend is up!</p>
          <pre style={{ background: '#f4f4f4', padding: '1rem' }}>
            {JSON.stringify(health.payload, null, 2)}
          </pre>
        </>
      )}
    </main>
  )
}

export default App
