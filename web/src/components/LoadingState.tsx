"use client";

import { Icon } from "./Icon";

/**
 * Vista de carga genérica y reutilizable, en la misma tónica visual que
 * `ErrorState` (glow degradado, centrada). `compact` la reduce para usarla
 * dentro de una tarjeta o sección en vez de ocupar toda la página.
 */
export function LoadingState({
  title = "Cargando…",
  message,
  icon = "auto_awesome",
  compact = false,
}: {
  title?: string;
  message?: string;
  icon?: string;
  compact?: boolean;
}) {
  return (
    <div
      className={`mx-auto flex w-full max-w-md flex-col items-center text-center ${
        compact ? "gap-4 py-8" : "min-h-[60vh] justify-center gap-6 px-4 py-16"
      }`}
    >
      <div className={`relative flex items-center justify-center ${compact ? "h-16 w-16" : "h-24 w-24"}`}>
        <div className="absolute inset-0 animate-pulse rounded-full bg-linear-to-br from-electric-indigo/25 to-vivid-cyan/25 blur-xl" />
        <div
          className={`relative flex items-center justify-center rounded-full bg-surface-container-lowest text-primary shadow-glow ring-1 ring-outline-variant/40 ${
            compact ? "h-14 w-14" : "h-20 w-20"
          }`}
        >
          <div className="absolute inset-0 animate-spin-slow rounded-full border-2 border-transparent border-t-primary border-r-primary [animation-duration:1.1s]" />
          <Icon name={icon} className={compact ? "text-[22px]" : "text-[30px]"} />
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
        {message && (
          <p className={compact ? "text-body-sm text-on-surface-variant" : "text-body-md text-on-surface-variant"}>
            {message}
          </p>
        )}
      </div>
    </div>
  );
}

/** Spinner inline mínimo para usar dentro de botones u otros elementos de una
 * sola línea, donde `LoadingState` sería demasiado — análogo a `ErrorBanner`. */
export function LoadingSpinner({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block h-4 w-4 shrink-0 animate-spin-slow rounded-full border-2 border-transparent border-t-current border-r-current [animation-duration:0.7s] ${className}`}
    />
  );
}
