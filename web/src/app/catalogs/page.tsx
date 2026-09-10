"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Fab } from "@/components/Fab";
import { Icon } from "@/components/Icon";
import { JobStatusChip } from "@/components/JobStatusChip";
import { LoadingState } from "@/components/LoadingState";
import { useToast } from "@/components/Toast";
import { absoluteUrl, deleteJob } from "@/lib/api";
import { useJobs } from "@/lib/hooks";
import type { JobSummary, JobStatus } from "@/lib/types";

type StatusFilter = "all" | JobStatus;

const FILTERS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "done", label: "Listos" },
  { value: "processing", label: "Procesando" },
  { value: "pending", label: "Pendientes" },
  { value: "failed", label: "Fallidos" },
];

export default function CatalogsPage() {
  const { data: jobs } = useJobs();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [pendingDeleteJob, setPendingDeleteJob] = useState<JobSummary | null>(null);
  const [deleting, setDeleting] = useState(false);
  const toast = useToast();

  const filteredJobs = useMemo(() => {
    if (!jobs) return undefined;
    const q = query.trim().toLowerCase();
    return jobs
      .filter((job) => statusFilter === "all" || job.status === statusFilter)
      .filter((job) => !q || (job.catalog_title ?? job.id).toLowerCase().includes(q))
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, [jobs, query, statusFilter]);

  async function confirmDeleteJob() {
    if (!pendingDeleteJob) return;
    setDeleting(true);
    try {
      await deleteJob(pendingDeleteJob.id);
      setPendingDeleteJob(null);
      toast.success("Catálogo eliminado.");
    } catch {
      toast.error("No se pudo eliminar el catálogo. Intenta de nuevo.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-(--container-max) space-y-8 px-4 py-12 sm:px-margin-desktop md:py-16">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-display-sm font-bold text-on-surface">Catálogos</h1>
            <p className="mt-1 text-body-md text-on-surface-variant">
              Todos los lotes que subiste, listos o en proceso.
            </p>
          </div>
          <Link
            href="/"
            className="flex w-fit items-center gap-2 rounded-lg gradient-ai px-5 py-2.5 font-semibold text-white shadow-glow transition hover:opacity-90"
          >
            <Icon name="add_circle" />
            Nuevo lote
          </Link>
        </div>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:max-w-xs">
            <Icon
              name="search"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant"
            />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar catálogo…"
              className="w-full rounded-lg border border-outline-variant bg-surface py-2.5 pl-10 pr-4 text-body-md text-on-surface outline-none placeholder:text-on-surface-variant focus:border-primary"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            {FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => setStatusFilter(f.value)}
                className={`rounded-full px-4 py-1.5 font-mono text-label-sm transition-colors ${
                  statusFilter === f.value
                    ? "bg-primary text-on-primary"
                    : "bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {!filteredJobs ? (
          <LoadingState compact title="Cargando…" />
        ) : filteredJobs.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-xl bg-surface p-16 text-center shadow-sm">
            <Icon name="storefront" className="text-4xl text-on-surface-variant" />
            <p className="text-body-md text-on-surface-variant">
              {jobs && jobs.length > 0
                ? "Ningún catálogo coincide con la búsqueda o el filtro."
                : "Todavía no creaste ningún lote. Sube fotos desde el dashboard para empezar."}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-gutter sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filteredJobs.map((job) => {
              const isDone = job.status === "done";
              const href = isDone ? `/jobs/${job.id}/catalog` : `/jobs/${job.id}/processing`;
              return (
                <Link
                  key={job.id}
                  href={href}
                  className="group relative flex flex-col overflow-hidden rounded-xl bg-surface shadow-sm transition-shadow hover:shadow-md"
                >
                  <div className="flex aspect-video w-full items-center justify-center overflow-hidden bg-surface-container-high">
                    {job.thumbnail_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={absoluteUrl(job.thumbnail_url) ?? undefined}
                        alt={job.catalog_title ?? job.id}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <Icon name="storefront" className="text-4xl text-on-surface-variant" />
                    )}
                    <div className="absolute right-3 top-3">
                      <JobStatusChip status={job.status} />
                    </div>
                  </div>
                  <div className="flex flex-1 items-start justify-between gap-2 p-4">
                    <div className="min-w-0">
                      <h4 className="truncate font-medium text-body-md text-on-surface">
                        {job.catalog_title ?? job.id}
                      </h4>
                      <p className="truncate text-body-sm text-on-surface-variant">
                        {job.products} producto{job.products === 1 ? "" : "s"} ·{" "}
                        {new Date(job.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        setPendingDeleteJob(job);
                      }}
                      title="Eliminar catálogo"
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-on-surface-variant opacity-0 transition-colors hover:bg-error hover:text-on-error group-hover:opacity-100"
                    >
                      <Icon name="delete" className="text-[18px]" />
                    </button>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      <Fab actions={[{ label: "Nuevo catálogo", icon: "add_circle", href: "/" }]} />

      {pendingDeleteJob && (
        <ConfirmDialog
          title="Eliminar catálogo"
          message={`¿Eliminar "${pendingDeleteJob.catalog_title ?? pendingDeleteJob.id}"? Se borrarán las fotos, imágenes generadas y el catálogo publicado. Esta acción no se puede deshacer.`}
          confirmLabel={deleting ? "Eliminando…" : "Eliminar"}
          onConfirm={confirmDeleteJob}
          onCancel={() => setPendingDeleteJob(null)}
        />
      )}
    </AppShell>
  );
}
