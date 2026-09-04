"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Icon } from "@/components/Icon";
import { JobStatusChip } from "@/components/JobStatusChip";
import { UploadDropzone } from "@/components/UploadDropzone";
import { BackgroundPicker, type BackgroundChoice } from "@/components/BackgroundPicker";
import { absoluteUrl, createJob, deleteJob, EXPLICIT_WHITE_BACKGROUND, KEEP_ORIGINAL_BACKGROUND } from "@/lib/api";
import { useBackgrounds, useJobs } from "@/lib/hooks";
import type { JobSummary } from "@/lib/types";

export default function DashboardPage() {
  const router = useRouter();
  const { data: jobs } = useJobs();
  const { data: backgrounds } = useBackgrounds();
  const doneJobs = jobs?.filter((j) => j.status === "done") ?? [];
  const otherJobs = jobs?.filter((j) => j.status !== "done") ?? [];
  const [files, setFiles] = useState<File[]>([]);
  const [fileBackgrounds, setFileBackgrounds] = useState<(string | null)[]>([]);
  // `null` = el usuario todavía no tocó el selector — se muestra/usa el fondo
  // marcado como "Por defecto" (si hay uno) en vez de guardar ese valor con
  // un efecto, que dispararía un set-state-in-effect por sincronizar estado
  // derivado de `backgrounds` en vez de calcularlo directo en el render.
  const [background, setBackground] = useState<BackgroundChoice | null>(null);
  const defaultBackground = backgrounds?.find((b) => b.is_default);
  const effectiveBackground: BackgroundChoice =
    background ?? (defaultBackground ? { mode: "saved", key: defaultBackground.background_key } : { mode: "none" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingDeleteJob, setPendingDeleteJob] = useState<JobSummary | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function confirmDeleteJob() {
    if (!pendingDeleteJob) return;
    setDeleting(true);
    try {
      await deleteJob(pendingDeleteJob.id);
      setPendingDeleteJob(null);
    } finally {
      setDeleting(false);
    }
  }

  async function handleSubmit() {
    if (files.length === 0) {
      setError("Selecciona al menos una foto para comenzar.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const job = await createJob({
        files,
        backgroundKey:
          effectiveBackground.mode === "saved"
            ? effectiveBackground.key
            : effectiveBackground.mode === "original"
              ? KEEP_ORIGINAL_BACKGROUND
              : background !== null
                ? EXPLICIT_WHITE_BACKGROUND
                : null,
        backgroundKeys: fileBackgrounds,
      });
      router.push(`/jobs/${job.id}/processing`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo crear el lote.");
      setSubmitting(false);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-(--container-max) space-y-16 px-4 py-12 sm:px-margin-desktop md:py-16">
        {/* Hero */}
        <div className="group relative">
          <div className="absolute -inset-1 rounded-xl bg-gradient-to-r from-electric-indigo to-vivid-cyan opacity-20 blur transition duration-1000 group-hover:opacity-40" />
          <div className="relative flex flex-col items-center justify-between gap-8 rounded-xl bg-surface p-8 shadow-sm md:flex-row md:p-12">
            <div className="max-w-2xl space-y-4">
              <span className="inline-flex items-center gap-2 rounded-full bg-surface-container-high px-3 py-1 font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
                <span className="h-2 w-2 animate-pulse rounded-full bg-ai-success" />
                Sistema IA activo
              </span>
              <h1 className="text-display-lg font-bold text-on-surface">
                Bienvenido a SnapFlick. Convierte fotos en catálogos.
              </h1>
              <p className="text-body-lg text-on-surface-variant">
                Sube las fotos de tus productos, selecciona un fondo de marca y deja que la IA
                genere un catálogo profesional en minutos.
              </p>
            </div>
            <div className="relative hidden h-48 w-48 shrink-0 items-center justify-center overflow-hidden rounded-full bg-surface-container-low shadow-inner lg:flex">
              <div className="absolute inset-0 animate-spin-slow bg-gradient-to-br from-primary/10 to-transparent" />
              <Icon name="auto_fix_high" className="relative z-10 text-6xl text-primary" filled />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-gutter lg:grid-cols-12">
          {/* Main: upload + background */}
          <div className="space-y-8 lg:col-span-8">
            <UploadDropzone
              files={files}
              onChange={setFiles}
              backgrounds={backgrounds ?? []}
              fileBackgrounds={fileBackgrounds}
              onFileBackgroundsChange={setFileBackgrounds}
            />
            <BackgroundPicker value={effectiveBackground} onChange={setBackground} />

            {error && <p className="text-body-md text-error">{error}</p>}

            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="flex w-fit items-center gap-2 rounded-lg gradient-ai px-6 py-3 font-semibold text-white shadow-glow transition hover:opacity-90 disabled:opacity-50"
            >
              <Icon name="auto_awesome" />
              {submitting ? "Creando lote…" : "Generar catálogo"}
            </button>
          </div>

          {/* Sidebar: catalogs + in-progress batches */}
          <div className="space-y-8 lg:col-span-4">
            <aside className="sticky top-24 space-y-8 rounded-xl bg-surface p-6 shadow-sm">
              <div>
                <h2 className="mb-4 text-headline-md font-semibold text-on-surface">Catálogos generados</h2>
                <div className="space-y-4">
                  {!jobs ? (
                    <p className="text-body-md text-on-surface-variant">Cargando…</p>
                  ) : doneJobs.length === 0 ? (
                    <p className="text-body-md text-on-surface-variant">
                      Todavía no hay catálogos terminados. Aparecerán aquí cuando un lote termine de procesarse.
                    </p>
                  ) : (
                    doneJobs.map((job) => (
                      <Link
                        key={job.id}
                        href={`/jobs/${job.id}/catalog`}
                        className="group relative flex items-center gap-4 rounded-lg border border-transparent p-3 transition-colors hover:border-outline-variant/30 hover:bg-surface-container-low"
                      >
                        <div className="h-14 w-14 shrink-0 overflow-hidden rounded-lg bg-surface-container-high">
                          {job.thumbnail_url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={absoluteUrl(job.thumbnail_url) ?? undefined}
                              alt={job.catalog_title ?? job.id}
                              className="h-full w-full object-cover"
                            />
                          ) : (
                            <div className="flex h-full w-full items-center justify-center text-on-surface-variant">
                              <Icon name="storefront" />
                            </div>
                          )}
                        </div>
                        <div className="min-w-0 flex-1">
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
                      </Link>
                    ))
                  )}
                </div>
              </div>

              {otherJobs.length > 0 && (
                <div className="border-t border-outline-variant/30 pt-6">
                  <h2 className="mb-4 text-headline-md font-semibold text-on-surface">En proceso</h2>
                  <div className="space-y-4">
                    {otherJobs.map((job) => (
                      <Link
                        key={job.id}
                        href={`/jobs/${job.id}/processing`}
                        className="group flex items-center justify-between gap-4 rounded-lg border border-transparent p-3 transition-colors hover:border-outline-variant/30 hover:bg-surface-container-low"
                      >
                        <div className="min-w-0">
                          <h4 className="truncate font-mono text-label-md text-on-surface">{job.id}</h4>
                          <p className="truncate text-body-md text-on-surface-variant">
                            {job.products} producto{job.products === 1 ? "" : "s"} ·{" "}
                            {new Date(job.created_at).toLocaleDateString()}
                          </p>
                        </div>
                        <JobStatusChip status={job.status} />
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </aside>
          </div>
        </div>
      </div>

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
