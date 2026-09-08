"use client";

import Link from "next/link";
import { Icon } from "./Icon";

/**
 * Vista de error genérica y reutilizable para toda la app: se usa tanto para
 * fallos de carga (SWR `error`) como para límites de error de Next.js
 * (`error.tsx`/`global-error.tsx`). `compact` la reduce para usarla dentro de
 * una tarjeta o sección en vez de ocupar toda la página.
 */
export function ErrorState({
  title = "Algo salió mal",
  message = "No pudimos completar esta acción. Intenta de nuevo en unos segundos.",
  icon = "sentiment_dissatisfied",
  details,
  onRetry,
  retryLabel = "Reintentar",
  actionHref,
  actionLabel,
  compact = false,
}: {
  title?: string;
  message?: string;
  icon?: string;
  details?: string;
  onRetry?: () => void;
  retryLabel?: string;
  actionHref?: string;
  actionLabel?: string;
  compact?: boolean;
}) {
  return (
    <div
      className={`mx-auto flex w-full max-w-md flex-col items-center text-center ${
        compact ? "gap-4 py-8" : "min-h-[60vh] justify-center gap-6 px-4 py-16"
      }`}
    >
      <div className={`relative flex items-center justify-center ${compact ? "h-16 w-16" : "h-24 w-24"}`}>
        <div className="absolute inset-0 rounded-full bg-linear-to-br from-electric-indigo/25 to-vivid-cyan/25 blur-xl" />
        <div
          className={`relative flex items-center justify-center rounded-full bg-surface-container-lowest text-primary shadow-glow ring-1 ring-outline-variant/40 ${
            compact ? "h-14 w-14" : "h-20 w-20"
          }`}
        >
          <Icon name={icon} className={compact ? "text-[26px]" : "text-[36px]"} />
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <h2
          className={
            compact
              ? "text-headline-sm font-semibold text-on-surface"
              : "text-headline-lg font-semibold text-on-surface"
          }
        >
          {title}
        </h2>
        <p className={compact ? "text-body-sm text-on-surface-variant" : "text-body-md text-on-surface-variant"}>
          {message}
        </p>
        {details && (
          <p className="mt-1 rounded-lg bg-surface-container-low px-3 py-2 font-mono text-label-sm text-on-surface-variant opacity-80">
            {details}
          </p>
        )}
      </div>
      {(onRetry || (actionHref && actionLabel)) && (
        <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
          {onRetry && (
            <button
              onClick={onRetry}
              className="flex items-center gap-2 rounded-full gradient-ai px-6 py-2.5 font-mono text-label-md text-white shadow-glow transition hover:opacity-90"
            >
              <Icon name="refresh" className="text-[18px]" />
              {retryLabel}
            </button>
          )}
          {actionHref && actionLabel && (
            <Link
              href={actionHref}
              className="rounded-full border border-outline-variant px-6 py-2.5 font-mono text-label-md text-on-surface transition-colors hover:bg-surface-container-high"
            >
              {actionLabel}
            </Link>
          )}
        </div>
      )}
    </div>
  );
}

/** Variante compacta para errores puntuales dentro de un flujo (formularios,
 * acciones inline) — una sola línea con ícono, sin ocupar toda la sección. */
export function ErrorBanner({ message, className = "" }: { message: string; className?: string }) {
  return (
    <div
      className={`flex items-start gap-2.5 rounded-xl bg-error-container px-4 py-3 text-on-error-container ${className}`}
    >
      <Icon name="error" className="mt-0.5 shrink-0 text-[18px] text-error" />
      <p className="text-body-sm">{message}</p>
    </div>
  );
}
