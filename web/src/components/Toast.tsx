"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";
import { Icon } from "./Icon";

type ToastKind = "success" | "error";

interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
}

const AUTO_DISMISS_MS = 4000;

const ToastContext = createContext<((kind: ToastKind, message: string) => void) | null>(null);

/** Se monta una sola vez en `AppShell` — toda la app pasa por ahí, así que
 * `useToast()` queda disponible en cualquier componente cliente sin tener
 * que envolver cada página por separado. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const show = useCallback(
    (kind: ToastKind, message: string) => {
      const id = nextId.current++;
      setToasts((current) => [...current, { id, kind, message }]);
      setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="fixed bottom-6 left-1/2 z-[60] flex w-full max-w-sm -translate-x-1/2 flex-col gap-2 px-4">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={`glass animate-step-pop flex items-start gap-2.5 rounded-xl border px-4 py-3 shadow-glow ${
              t.kind === "success" ? "border-ai-success/30" : "border-error/30"
            }`}
          >
            <Icon
              name={t.kind === "success" ? "check_circle" : "error"}
              className={`mt-0.5 shrink-0 text-[18px] ${t.kind === "success" ? "text-ai-success" : "text-error"}`}
              filled={t.kind === "success"}
            />
            <p className="flex-1 text-body-sm text-on-surface">{t.message}</p>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              aria-label="Cerrar"
              className="shrink-0 text-on-surface-variant transition-colors hover:text-on-surface"
            >
              <Icon name="close" className="text-[16px]" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const show = useContext(ToastContext);
  if (!show) throw new Error("useToast debe usarse dentro de <ToastProvider>");
  return {
    success: (message: string) => show("success", message),
    error: (message: string) => show("error", message),
  };
}
