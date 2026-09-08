"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { ErrorState } from "@/components/ErrorState";
import { Icon } from "@/components/Icon";
import { absoluteUrl } from "@/lib/api";
import { useJob } from "@/lib/hooks";

const STEPS = [
  { key: "cutout", label: "Removiendo fondos", detail: "Identificando sujetos principales.", icon: "content_cut" },
  { key: "compose", label: "Composición de marca", detail: "Aplicando el fondo y estilo visual.", icon: "settings_b_roll" },
  { key: "vision", label: "Lectura con IA", detail: "Extrayendo información del empaque.", icon: "barcode_reader" },
  { key: "catalog", label: "Categorización", detail: "Agrupando el catálogo por categorías.", icon: "category" },
] as const;

function currentStepIndex(pct: number) {
  if (pct >= 95) return 3;
  if (pct >= 60) return 2;
  if (pct >= 25) return 1;
  return 0;
}

export function ProcessingClient({ jobId }: { jobId: string }) {
  const router = useRouter();
  const { data: job, error } = useJob(jobId);

  useEffect(() => {
    if (job?.status === "done") router.replace(`/jobs/${jobId}/review`);
  }, [job?.status, jobId, router]);

  if (error) {
    return (
      <AppShell>
        <ErrorState
          title="No se pudo consultar el lote"
          message="Revisa tu conexión e intenta de nuevo."
          actionHref="/"
          actionLabel="Volver al inicio"
        />
      </AppShell>
    );
  }
  if (!job) {
    return (
      <AppShell>
        <p className="p-8 text-body-md text-on-surface-variant">Cargando…</p>
      </AppShell>
    );
  }

  if (job.status === "failed") {
    return (
      <AppShell>
        <div className="mx-auto max-w-2xl px-4 py-16 text-center">
          <h1 className="text-headline-lg font-semibold text-error">El lote falló</h1>
          <ul className="mt-6 flex flex-col gap-3 text-left">
            {job.errors.map((e, i) => {
              const [file, ...rest] = e.split(": ");
              const message = rest.join(": ") || file;
              return (
                <li
                  key={i}
                  className="flex items-start gap-3 rounded-lg bg-error-container p-4 text-on-error-container"
                >
                  <Icon name="error" className="mt-0.5 shrink-0 text-error" />
                  <div className="flex flex-col">
                    {rest.length > 0 && (
                      <span className="font-mono text-label-sm opacity-70">{file}</span>
                    )}
                    <span className="text-body-md">{message}</span>
                  </div>
                </li>
              );
            })}
          </ul>
          <Link href="/" className="mt-6 inline-block font-semibold text-primary">
            Intentar de nuevo →
          </Link>
        </div>
      </AppShell>
    );
  }

  const pct = job.total_images > 0 ? Math.round((job.processed_images / job.total_images) * 100) : 0;
  const active = currentStepIndex(pct);
  const placeholders = Math.max(0, job.total_images - job.products.length);

  return (
    <AppShell>
      <div className="relative flex w-full flex-col overflow-hidden">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute left-1/4 top-1/4 h-96 w-96 rounded-full bg-primary-container opacity-20 blur-[120px]" />
          <div className="absolute bottom-1/4 right-1/4 h-[30rem] w-[30rem] rounded-full bg-secondary-container opacity-10 blur-[150px]" />
        </div>

        <div className="relative z-10 mx-auto w-full max-w-(--container-max) flex-1 px-gutter py-12">
          <div className="flex flex-col gap-gutter md:flex-row">
            <div className="flex w-full flex-col gap-8 md:w-1/3">
              <div className="relative overflow-hidden rounded-3xl bg-surface p-8 shadow-xl">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-transparent opacity-50" />
                <div className="relative z-10 flex flex-col gap-6">
                  <div className="flex items-center gap-4">
                    <div className="flex h-12 w-12 animate-pulse items-center justify-center rounded-xl bg-primary-container text-on-primary-container shadow-lg">
                      <Icon name="auto_awesome" filled />
                    </div>
                    <div className="flex flex-col">
                      <span className="font-mono text-label-sm uppercase tracking-widest text-primary">Estado</span>
                      <h1 className="text-headline-md font-semibold text-on-surface">Procesando</h1>
                    </div>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-surface-container-high">
                    <div className="h-full gradient-ai rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="flex items-center justify-between font-mono text-label-md text-on-surface-variant">
                    <span>{STEPS[active].label}...</span>
                    <span className="font-bold text-primary">{pct}%</span>
                  </div>
                </div>
              </div>

              <div className="relative z-10 flex-1 rounded-3xl bg-surface p-8 shadow-lg">
                <h2 className="mb-6 text-body-lg font-semibold text-on-surface">Operaciones IA</h2>
                <div className="relative flex flex-col gap-2">
                  <div className="absolute bottom-4 left-4 top-4 w-px bg-surface-container-high" />
                  {STEPS.map((step, i) => {
                    const done = i < active;
                    const isActive = i === active;
                    return (
                      <div
                        key={step.key}
                        className={`relative z-10 flex gap-4 rounded-xl p-4 transition-all duration-300 ${
                          isActive
                            ? "scale-105 border border-primary/20 bg-primary-container/10 shadow-md"
                            : done
                              ? "bg-surface-container-low"
                              : "opacity-60"
                        }`}
                      >
                        <div
                          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full shadow-md ${
                            done
                              ? "bg-ai-success text-on-secondary"
                              : isActive
                                ? "animate-pulse bg-primary text-on-primary ring-4 ring-primary/20"
                                : "bg-surface-container-highest text-on-surface-variant"
                          }`}
                        >
                          <Icon name={done ? "check" : step.icon} className="text-sm" />
                        </div>
                        <div className="flex flex-col">
                          <span
                            className={`font-mono text-label-md ${isActive ? "font-bold text-primary" : "text-on-surface"}`}
                          >
                            {step.label}
                          </span>
                          <span className="text-sm text-on-surface-variant opacity-80">{step.detail}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="flex w-full flex-col gap-6 md:w-2/3">
              <div className="flex items-end justify-between">
                <h2 className="text-display-lg leading-none text-on-surface">
                  Resultados
                  <br />
                  <span className="text-primary opacity-60">en tiempo real</span>
                </h2>
                <div className="rounded-full bg-surface-container px-4 py-2 font-mono text-label-md text-on-surface-variant shadow-sm">
                  {job.processed_images} / {job.total_images} procesados
                </div>
              </div>

              <div className="grid auto-rows-[200px] grid-cols-2 gap-6 lg:grid-cols-3">
                {job.products.map((p) => {
                  const thumb = absoluteUrl(p.image.thumbnail_path ?? p.image.composed_path);
                  return (
                    <div key={p.id} className="group relative overflow-hidden rounded-2xl bg-surface shadow-md">
                      {thumb ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={thumb} alt={p.sheet.name} className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105" />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center bg-surface-container-low text-on-surface-variant">
                          <Icon name="error" className="text-error" />
                        </div>
                      )}
                      <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
                      <div className="absolute bottom-0 left-0 w-full p-4">
                        <span className="rounded-md bg-ai-success/80 px-2 py-1 font-mono text-label-sm text-white backdrop-blur-md">
                          Completado
                        </span>
                      </div>
                    </div>
                  );
                })}
                {Array.from({ length: placeholders }).map((_, i) => (
                  <div
                    key={`ph-${i}`}
                    className="flex items-center justify-center rounded-2xl border border-dashed border-outline-variant/50 bg-surface-container-low"
                  >
                    <div className="flex flex-col items-center gap-2 text-on-surface-variant opacity-50">
                      <Icon name="hourglass_empty" className="text-4xl" />
                      <span className="font-mono text-label-md">En espera</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
