import { useEffect, useRef, useState } from 'react'
import { arenaSocketUrl } from '../api'

/**
 * Connects to /api/ws/arena and keeps the most recent event plus a
 * short rolling log. Reconnects automatically with backoff if the
 * connection drops — the backend engine survives across reconnects
 * since state lives server-side, not in this hook.
 */
export function useArenaSocket() {
  const [lastEvent, setLastEvent] = useState(null)
  const [connected, setConnected] = useState(false)
  const [log, setLog] = useState([])
  const retryDelay = useRef(1000)

  useEffect(() => {
    let socket
    let closedByEffect = false
    let retryTimer

    function connect() {
      socket = new WebSocket(arenaSocketUrl())

      socket.onopen = () => {
        setConnected(true)
        retryDelay.current = 1000
      }

      socket.onmessage = (event) => {
        const parsed = JSON.parse(event.data)
        setLastEvent(parsed)
        setLog((prev) => [...prev.slice(-49), parsed])
      }

      socket.onclose = () => {
        setConnected(false)
        if (!closedByEffect) {
          retryTimer = setTimeout(connect, retryDelay.current)
          retryDelay.current = Math.min(retryDelay.current * 1.5, 10000)
        }
      }

      socket.onerror = () => socket.close()
    }

    connect()

    return () => {
      closedByEffect = true
      clearTimeout(retryTimer)
      socket?.close()
    }
  }, [])

  return { lastEvent, connected, log }
}
