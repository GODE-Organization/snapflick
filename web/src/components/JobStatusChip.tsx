import type { JobStatus } from "@/lib/types";

const STYLES: Record<JobStatus, { label: string; className: string }> = {
  pending: { label: "Pendiente", className: "bg-outline-variant/30 text-on-surface-variant" },
  processing: { label: "Procesando", className: "bg-primary/10 text-primary animate-pulse" },
  done: { label: "Listo", className: "bg-ai-success/10 text-ai-success" },
  failed: { label: "Falló", className: "bg-error/10 text-error" },
};

export function JobStatusChip({ status }: { status: JobStatus }) {
  const { label, className } = STYLES[status];
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 font-mono text-label-sm ${className}`}
    >
      {label}
    </span>
  );
}
