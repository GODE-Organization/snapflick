"use client";

import { useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { Icon } from "@/components/Icon";
import { ProductDetailModal } from "@/components/ProductDetailModal";
import { absoluteUrl } from "@/lib/api";
import { useJob } from "@/lib/hooks";
import type { ProductRecord } from "@/lib/types";

export function CatalogClient({ jobId }: { jobId: string }) {
  const { data: job, error } = useJob(jobId);
  const [selected, setSelected] = useState<ProductRecord | null>(null);
  const [copied, setCopied] = useState(false);
  const [preview, setPreview] = useState<"desktop" | "mobile">("desktop");
  const [activeCategory, setActiveCategory] = useState<string>("Todos");

  if (error) {
    return (
      <AppShell>
        <p className="p-8 text-body-md text-error">No se pudo cargar el catálogo.</p>
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

  if (job.status !== "done") {
    return (
      <AppShell>
        <div className="mx-auto max-w-2xl px-4 py-16 text-center">
          <p className="text-body-lg text-on-surface-variant">
            El catálogo todavía no está listo para este lote.
          </p>
          <Link href={`/jobs/${jobId}/processing`} className="mt-4 inline-block font-semibold text-primary">
            Ver progreso →
          </Link>
        </div>
      </AppShell>
    );
  }

  const publicUrl = absoluteUrl(job.catalog_html_path);
  const jsonUrl = job.catalog_html_path
    ? absoluteUrl(job.catalog_html_path.replace(/catalogo\.html$/, "catalogo.json"))
    : null;
  const categories = job.plan?.categories ?? [
    ...new Set(job.products.map((p) => p.sheet.category ?? "Sin categoría")),
  ];
  const visible =
    activeCategory === "Todos"
      ? job.products
      : job.products.filter((p) => (p.sheet.category ?? "Sin categoría") === activeCategory);

  async function copyLink() {
    if (!publicUrl) return;
    await navigator.clipboard.writeText(publicUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <AppShell>
      <div className="relative w-full">
        <div aria-hidden className="pointer-events-none fixed -z-10 h-full w-full bg-gradient-to-br from-background via-surface-container-low to-background" />
        <div className="mx-auto w-full max-w-(--container-max) space-y-12 px-4 py-12 sm:px-margin-desktop">
          <div className="relative flex flex-col items-start justify-between gap-6 md:flex-row md:items-end">
            <div className="max-w-2xl space-y-4">
              <div className="flex items-center gap-3">
                <span className="rounded-full bg-ai-success/10 px-3 py-1 font-mono text-label-sm text-ai-success">
                  Estado: Listo
                </span>
                <span className="rounded-full bg-surface-container-highest px-3 py-1 font-mono text-label-sm text-on-surface-variant">
                  {job.products.length} productos
                </span>
              </div>
              <h1 className="text-display-lg font-bold text-on-background">
                {job.plan?.catalog_title ?? "Catálogo"}
              </h1>
              {job.plan?.catalog_summary && (
                <p className="text-body-lg text-on-surface-variant">{job.plan.catalog_summary}</p>
              )}
            </div>
            {publicUrl && (
              <div className="flex min-w-[320px] flex-col gap-3">
                <label className="pl-1 font-mono text-label-sm uppercase tracking-widest text-on-surface-variant">
                  Enlace público
                </label>
                <div className="flex items-center rounded-xl bg-surface-container-lowest p-1 shadow-sm">
                  <Icon name="link" className="px-3 text-outline" />
                  <input
                    readOnly
                    value={publicUrl}
                    className="w-full truncate border-none bg-transparent py-2 font-mono text-label-md text-on-background outline-none"
                  />
                  <button
                    onClick={copyLink}
                    className="shrink-0 rounded-lg bg-primary px-4 py-2 font-mono text-label-md text-on-primary shadow-md transition-colors hover:bg-primary/90"
                  >
                    {copied ? "¡Listo!" : "Copiar"}
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 items-start gap-8 xl:grid-cols-12">
            {/* Sidebar */}
            <div className="space-y-6 xl:sticky xl:top-24 xl:col-span-3">
              <div className="space-y-6 rounded-xl bg-surface-container-lowest p-6 shadow-sm">
                <div>
                  <h3 className="mb-4 font-mono text-label-md uppercase tracking-widest text-on-surface-variant">
                    Vista previa
                  </h3>
                  <div className="flex rounded-lg bg-surface-container p-1">
                    <button
                      onClick={() => setPreview("desktop")}
                      className={`flex flex-1 items-center justify-center gap-2 rounded-md py-2 font-mono text-label-md transition-all ${
                        preview === "desktop" ? "bg-surface-container-lowest text-primary shadow-sm" : "text-on-surface-variant"
                      }`}
                    >
                      <Icon name="desktop_windows" className="text-sm" />
                      Desktop
                    </button>
                    <button
                      onClick={() => setPreview("mobile")}
                      className={`flex flex-1 items-center justify-center gap-2 rounded-md py-2 font-mono text-label-md transition-all ${
                        preview === "mobile" ? "bg-surface-container-lowest text-primary shadow-sm" : "text-on-surface-variant"
                      }`}
                    >
                      <Icon name="smartphone" className="text-sm" />
                      Mobile
                    </button>
                  </div>
                </div>

                <div className="h-px w-full bg-surface-container-highest" />

                <div>
                  <h3 className="mb-4 font-mono text-label-md uppercase tracking-widest text-on-surface-variant">
                    Exportar
                  </h3>
                  <div className="space-y-2">
                    {jsonUrl && (
                      <a
                        href={jsonUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="group flex w-full items-center justify-between rounded-lg p-3 text-left transition-colors hover:bg-surface-container"
                      >
                        <div className="flex items-center gap-3">
                          <div className="flex h-8 w-8 items-center justify-center rounded bg-surface-container-high text-on-surface">
                            <Icon name="code" className="text-sm" />
                          </div>
                          <span className="font-mono text-label-md text-on-background">JSON completo</span>
                        </div>
                        <Icon name="download" className="text-on-surface-variant opacity-0 transition-opacity group-hover:opacity-100" />
                      </a>
                    )}
                    <div className="flex w-full cursor-not-allowed items-center justify-between rounded-lg p-3 opacity-40" title="Próximamente">
                      <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded bg-error-container text-on-error-container">
                          <Icon name="picture_as_pdf" className="text-sm" />
                        </div>
                        <span className="font-mono text-label-md text-on-background">Imprimir PDF</span>
                      </div>
                    </div>
                  </div>
                </div>

                {publicUrl && (
                  <>
                    <div className="h-px w-full bg-surface-container-highest" />
                    <a
                      href={publicUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="flex w-full items-center justify-center gap-2 rounded-xl gradient-ai py-3 font-semibold text-white shadow-glow transition-all hover:-translate-y-0.5"
                    >
                      <Icon name="storefront" />
                      Ver como cliente
                    </a>
                  </>
                )}
              </div>
            </div>

            {/* Preview */}
            <div className="xl:col-span-9">
              <div
                className={`mx-auto rounded-2xl bg-surface-container-lowest p-8 shadow-xl ring-1 ring-surface-container-highest transition-all duration-500 md:p-12 ${
                  preview === "mobile" ? "max-w-sm rounded-[2.5rem]" : "max-w-none"
                }`}
              >
                <nav className="hide-scrollbar mb-8 -mx-4 flex gap-2 overflow-x-auto px-4 pb-4">
                  <button
                    onClick={() => setActiveCategory("Todos")}
                    className={`whitespace-nowrap rounded-full px-6 py-2 font-mono text-label-md transition-colors ${
                      activeCategory === "Todos" ? "bg-primary text-on-primary shadow-md" : "bg-surface-container text-on-surface hover:bg-surface-container-high"
                    }`}
                  >
                    Todos
                  </button>
                  {categories.map((cat) => (
                    <button
                      key={cat}
                      onClick={() => setActiveCategory(cat)}
                      className={`whitespace-nowrap rounded-full px-6 py-2 font-mono text-label-md transition-colors ${
                        activeCategory === cat ? "bg-primary text-on-primary shadow-md" : "bg-surface-container text-on-surface hover:bg-surface-container-high"
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </nav>

                <div className={`grid gap-6 ${preview === "mobile" ? "grid-cols-1" : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"}`}>
                  {visible.map((p) => {
                    const thumb = absoluteUrl(p.image.thumbnail_path ?? p.image.composed_path);
                    return (
                      <button
                        key={p.id}
                        onClick={() => setSelected(p)}
                        className="group relative overflow-hidden rounded-2xl bg-surface text-left transition-all hover:-translate-y-1 hover:shadow-xl"
                      >
                        <div className="relative aspect-square overflow-hidden bg-surface-variant">
                          {thumb && (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={thumb} alt={p.sheet.name} className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105" />
                          )}
                          <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
                        </div>
                        <div className="p-5">
                          <div className="mb-2 flex items-start justify-between gap-2">
                            <h4 className="line-clamp-1 text-headline-md font-semibold text-on-background">{p.sheet.name}</h4>
                          </div>
                          {p.sheet.category && (
                            <span className="mb-2 inline-block rounded bg-primary/10 px-2 py-1 font-mono text-label-sm text-primary">
                              {p.sheet.category}
                            </span>
                          )}
                          <p className="line-clamp-2 text-body-md text-on-surface-variant">{p.sheet.description}</p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {selected && <ProductDetailModal product={selected} onClose={() => setSelected(null)} />}
    </AppShell>
  );
}
