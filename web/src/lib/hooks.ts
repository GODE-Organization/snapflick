import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { WS_URL, getAgentSettings, listBackgrounds } from "./api";
import type { Job, JobSummary } from "./types";

const RECONNECT_DELAY_MS = 2000;

interface SocketResult<T> {
  data: T | undefined;
  error: Error | null;
  /** Aplica un valor localmente sin esperar al servidor (p.ej. tras un PATCH optimista). */
  mutate: (value: T) => void;
}

/**
 * Suscripción WebSocket a un endpoint `/ws/...` que empuja el estado completo
 * cada vez que cambia. Reemplaza el polling por `refreshInterval` de SWR que
 * usábamos antes: en vez de que el cliente pregunte cada 2-5s, el servidor
 * empuja solo cuando algo cambió de verdad (ver `ConnectionManager` en
 * `agent/src/snapflick/main.py`).
 */
function useJobSocket<T>(path: string | null): SocketResult<T> {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<Error | null>(null);

  // Evita que un mensaje de un socket viejo (a punto de cerrarse por un
  // cambio de `path`) pise el estado del socket nuevo.
  const generationRef = useRef(0);

  useEffect(() => {
    if (!path) return;

    const generation = ++generationRef.current;
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let stopped = false;

    function connect() {
      socket = new WebSocket(`${WS_URL}${path}`);

      socket.onmessage = (event) => {
        if (generationRef.current !== generation) return;
        try {
          setData(JSON.parse(event.data) as T);
          setError(null);
        } catch {
          // ignora mensajes que no sean JSON válido
        }
      };
      socket.onerror = () => {
        if (generationRef.current !== generation) return;
        setError(new Error("Error de conexión en tiempo real"));
      };
      socket.onclose = () => {
        if (stopped || generationRef.current !== generation) return;
        retryTimer = setTimeout(connect, RECONNECT_DELAY_MS);
      };
    }

    connect();

    return () => {
      stopped = true;
      if (retryTimer) clearTimeout(retryTimer);
      // Cerrar un socket todavía CONNECTING (típico en dev: StrictMode monta
      // el efecto, lo limpia y lo vuelve a montar de inmediato) hace que el
      // navegador loguee "WebSocket is closed before the connection is
      // established". Es inofensivo, pero se evita esperando a que abra.
      if (socket?.readyState === WebSocket.CONNECTING) {
        socket.addEventListener("open", () => socket?.close());
      } else {
        socket?.close();
      }
    };
  }, [path]);

  const mutate = (value: T) => setData(value);

  return { data: path ? data : undefined, error, mutate };
}

export function useJobs(): SocketResult<JobSummary[]> {
  return useJobSocket<JobSummary[]>("/ws/jobs");
}

export function useJob(id: string | undefined): SocketResult<Job> {
  return useJobSocket<Job>(id ? `/ws/jobs/${id}` : null);
}

export function useBackgrounds() {
  return useSWR("backgrounds", listBackgrounds);
}

export function useAgentSettings() {
  return useSWR("agent-settings", getAgentSettings);
}
