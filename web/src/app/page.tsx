"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Icon } from "@/components/Icon";
import { JobStatusChip } from "@/components/JobStatusChip";
import { UploadDropzone } from "@/components/UploadDropzone";
import { BackgroundPicker, type BackgroundChoice } from "@/components/BackgroundPicker";
import { createJob } from "@/lib/api";
import { useJobs } from "@/lib/hooks";

export default function DashboardPage() {
  const router = useRouter();
  const { data: jobs } = useJobs();
  const [files, setFiles] = useState<File[]>([]);
  const [background, setBackground] = useState<BackgroundChoice>({ mode: "none" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
        backgroundFile: background.mode === "upload" ? background.file : null,
        backgroundKey: background.mode === "saved" ? background.key : null,
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
            <UploadDropzone files={files} onChange={setFiles} />
            <BackgroundPicker value={background} onChange={setBackground} />

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

          {/* Sidebar: recent projects */}
          <div className="lg:col-span-4">
            <aside className="sticky top-24 rounded-xl bg-surface p-6 shadow-sm">
              <div className="mb-6 flex items-center justify-between">
                <h2 className="text-headline-md font-semibold text-on-surface">Lotes recientes</h2>
              </div>
              <div className="space-y-4">
                {!jobs || jobs.length === 0 ? (
                  <p className="text-body-md text-on-surface-variant">
                    Todavía no has creado ningún lote. Sube tus primeras fotos para empezar.
                  </p>
                ) : (
                  jobs.map((job) => {
                    const href =
                      job.status === "done" ? `/jobs/${job.id}/catalog` : `/jobs/${job.id}/processing`;
                    return (
                      <Link
                        key={job.id}
                        href={href}
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
                    );
                  })
                )}
              </div>
            </aside>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
