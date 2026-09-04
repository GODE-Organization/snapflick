"use client";

import { Icon } from "./Icon";

/** Diálogo de confirmación genérico, estilo consistente con el resto de los
 * modales (glass, rounded-[24px], shadow-glow) — reemplaza `window.confirm()`,
 * que no se puede estilizar ni encaja con el resto de la UI. */
export function ConfirmDialog({
  title,
  message,
  confirmLabel = "Eliminar",
  cancelLabel = "Cancelar",
  danger = true,
  onConfirm,
  onCancel,
}: {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-inverse-surface/40 p-4"
      onClick={onCancel}
    >
      <div
        className="glass w-full max-w-sm rounded-[24px] border border-outline-variant/40 p-8 text-center shadow-glow"
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className={`mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full ${
            danger ? "bg-error-container text-on-error-container" : "bg-primary-container text-on-primary-container"
          }`}
        >
          <Icon name={danger ? "delete" : "help"} className="text-[28px]" />
        </div>
        <h2 className="text-headline-md font-semibold text-on-surface">{title}</h2>
        <p className="mt-2 text-body-sm text-on-surface-variant">{message}</p>
        <div className="mt-8 flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 rounded-full border border-outline-variant px-5 py-2.5 font-mono text-label-md text-on-surface transition-colors hover:bg-surface-container-high"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={`flex-1 rounded-full px-5 py-2.5 font-mono text-label-md shadow-md transition-colors ${
              danger ? "bg-error text-on-error hover:bg-error/90" : "bg-primary text-on-primary hover:bg-primary/90"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
