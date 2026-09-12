"use client";

import JSZip from "jszip";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { AddProductModal } from "@/components/AddProductModal";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ErrorBanner, ErrorState } from "@/components/ErrorState";
import { Fab } from "@/components/Fab";
import { Icon } from "@/components/Icon";
import { LoadingState } from "@/components/LoadingState";
import { ProductEditModal } from "@/components/ProductEditModal";
import { useToast } from "@/components/Toast";
import { absoluteUrl, addProduct, deleteJob, deleteProduct, updateCatalog } from "@/lib/api";
import { useJob } from "@/lib/hooks";
import type { Job, ProductRecord } from "@/lib/types";

const PRODUCTS_PAGE_SIZE = 6;

export function CatalogClient({ jobId }: { jobId: string }) {
  const router = useRouter();
  const { data: job, error, mutate } = useJob(jobId);
  const [selected, setSelected] = useState<ProductRecord | null>(null);
  const [copied, setCopied] = useState(false);
  const [preview, setPreview] = useState<"desktop" | "mobile">("desktop");
  const [activeCategory, setActiveCategory] = useState<string>("Todos");
  const [searchQuery, setSearchQuery] = useState("");
  const [visibilityFilter, setVisibilityFilter] = useState<"all" | "visible" | "hidden">("all");
  const [visibleCount, setVisibleCount] = useState(PRODUCTS_PAGE_SIZE);
  const [editingMeta, setEditingMeta] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [summaryDraft, setSummaryDraft] = useState("");
  const [savingMeta, setSavingMeta] = useState(false);
  const [pendingUpload, setPendingUpload] = useState<{
    previewUrl: string;
    uploadPromise: Promise<Job>;
  } | null>(null);
  const [pendingDelete, setPendingDelete] = useState<ProductRecord | null>(null);
  const [pendingDeleteCatalog, setPendingDeleteCatalog] = useState(false);
  const [deletingCatalog, setDeletingCatalog] = useState(false);
  const [downloadingImages, setDownloadingImages] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();

  if (error) {
    return (
      <AppShell>
        <ErrorState
          title="No se pudo cargar el catálogo"
          message="Se perdió la conexión en tiempo real. Intentando reconectar…"
          actionHref="/"
          actionLabel="Volver al inicio"
        />
      </AppShell>
    );
  }
  if (!job) {
    return (
      <AppShell>
        <LoadingState title="Cargando catálogo…" />
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

  // Ruta pública propia del sitio (`web/src/app/c/[jobId]`), no el HTML
  // autocontenido que sigue generando el agente (ese solo se mantiene para no
  // romper links ya compartidos). `window` porque este componente es
  // client-only y necesitamos el origen real (dev/staging/prod).
  const publicUrl = typeof window !== "undefined" ? `${window.location.origin}/c/${jobId}` : null;
  //const jsonUrl = absoluteUrl(job.catalog_json_path);
  const pdfUrl = absoluteUrl(job.catalog_pdf_path);
  const categories = job.plan?.categories ?? [
    ...new Set(job.products.map((p) => p.sheet.category ?? "Sin categoría")),
  ];
  const normalizedQuery = searchQuery.trim().toLowerCase();
  const filteredProducts = job.products.filter((p) => {
    const matchesCategory =
      activeCategory === "Todos" || (p.sheet.category ?? "Sin categoría") === activeCategory;
    const matchesVisibility =
      visibilityFilter === "all" || (visibilityFilter === "visible" ? p.visible : !p.visible);
    const matchesSearch =
      !normalizedQuery ||
      [p.sheet.name, p.sheet.brand, p.sheet.presentation, p.sheet.description, ...p.sheet.keywords]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery);
    return matchesCategory && matchesVisibility && matchesSearch;
  });
  const visibleProducts = filteredProducts.slice(0, visibleCount);
  const hasMoreProducts = filteredProducts.length > visibleCount;

  function resetPagination() {
    setVisibleCount(PRODUCTS_PAGE_SIZE);
  }

  async function copyLink() {
    if (!publicUrl) return;
    try {
      await navigator.clipboard.writeText(publicUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("No se pudo copiar el link.");
    }
  }

  function startEditingMeta() {
    if (!job) return;
    setTitleDraft(job.plan?.catalog_title ?? "");
    setSummaryDraft(job.plan?.catalog_summary ?? "");
    setEditingMeta(true);
  }

  async function saveMeta() {
    const title = titleDraft.trim();
    const summary = summaryDraft.trim();
    if (!job || !title) return;
    const patch: { catalog_title?: string; catalog_summary?: string } = {};
    if (title !== job.plan?.catalog_title) patch.catalog_title = title;
    if (summary !== job.plan?.catalog_summary) patch.catalog_summary = summary;
    if (Object.keys(patch).length === 0) {
      setEditingMeta(false);
      return;
    }
    setSavingMeta(true);
    try {
      mutate(await updateCatalog(jobId, patch));
      setEditingMeta(false);
      toast.success("Catálogo actualizado.");
    } catch {
      toast.error("No se pudo guardar. Intenta de nuevo.");
    } finally {
      setSavingMeta(false);
    }
  }

  async function confirmDeleteProduct() {
    if (!pendingDelete) return;
    const product = pendingDelete;
    setPendingDelete(null);
    try {
      const updated = await deleteProduct(jobId, product.id);
      mutate(updated);
      if (selected?.id === product.id) setSelected(null);
      toast.success("Producto eliminado.");
    } catch {
      toast.error("No se pudo eliminar el producto. Intenta de nuevo.");
    }
  }

  async function confirmDeleteCatalog() {
    setDeletingCatalog(true);
    try {
      await deleteJob(jobId);
      router.push("/");
    } catch {
      toast.error("No se pudo eliminar el catálogo. Intenta de nuevo.");
    } finally {
      setDeletingCatalog(false);
    }
  }

  function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    // El POST se despacha acá, en el evento síncrono de selección — no dentro
    // de un efecto del modal. `add_product_to_job` no es idempotente, y un
    // efecto con StrictMode (monta, limpia, remonta en desarrollo) lo
    // mandaría dos veces de verdad, duplicando el producto en el catálogo.
    setPendingUpload({ previewUrl: URL.createObjectURL(file), uploadPromise: addProduct(jobId, file) });
  }

  function closePendingUpload() {
    if (pendingUpload) URL.revokeObjectURL(pendingUpload.previewUrl);
    setPendingUpload(null);
  }

  async function downloadImagesZip() {
    if (!job || downloadingImages) return;
    setDownloadingImages(true);
    setDownloadError(null);
    try {
      const zip = new JSZip();
      const usedNames = new Set<string>();
      let failedCount = 0;
      await Promise.all(
        job.products
          .filter((p) => p.visible)
          .map(async (p) => {
            try {
              const url = absoluteUrl(p.image.composed_path ?? p.image.source_path);
              if (!url) return;
              const res = await fetch(url);
              if (!res.ok) throw new Error(`${res.status}`);
              const blob = await res.blob();
              const ext = blob.type.split("/")[1]?.split("+")[0] || "jpg";
              const base = p.sheet.name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || p.id;
              let name = `${base}.${ext}`;
              let i = 2;
              while (usedNames.has(name)) {
                name = `${base}-${i}.${ext}`;
                i += 1;
              }
              usedNames.add(name);
              zip.file(name, blob);
            } catch {
              // Una imagen individual que falla (borrada del disco, red intermitente)
              // no debe tirar abajo el .zip completo del resto de productos.
              failedCount += 1;
            }
          }),
      );
      if (usedNames.size === 0) {
        setDownloadError("No se pudo descargar ninguna imagen.");
        return;
      }
      const content = await zip.generateAsync({ type: "blob" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(content);
      link.download = `${job.plan?.catalog_title ?? job.id}-imagenes.zip`;
      link.click();
      URL.revokeObjectURL(link.href);
      if (failedCount > 0) {
        setDownloadError(`Se descargaron ${usedNames.size} imágenes; ${failedCount} no se pudieron incluir.`);
      }
    } catch {
      setDownloadError("No se pudo generar el .zip de imágenes.");
    } finally {
      setDownloadingImages(false);
    }
  }

  return (
    <AppShell>
      <div className="relative w-full">
        <div aria-hidden className="pointer-events-none fixed -z-10 h-full w-full bg-gradient-to-br from-background via-surface-container-low to-background" />
        <div className="mx-auto w-full max-w-(--container-max) space-y-12 px-4 py-12 sm:px-margin-desktop">
          <Link
            href="/catalogs"
            className="inline-flex w-fit items-center gap-2 font-mono text-label-md text-on-surface-variant transition-colors hover:text-primary"
          >
            <Icon name="arrow_back" className="text-[18px]" />
            Volver a catálogos
          </Link>

          <div className="relative flex flex-col items-start justify-between gap-6 md:flex-row md:items-end">
            <div className="min-w-0 flex-1 space-y-4">
              <div className="flex items-center gap-3">
                <span className="rounded-full bg-ai-success/10 px-3 py-1 font-mono text-label-sm text-ai-success">
                  Estado: Listo
                </span>
                <span className="rounded-full bg-surface-container-highest px-3 py-1 font-mono text-label-sm text-on-surface-variant">
                  {job.products.length} productos
                </span>
              </div>
              {editingMeta ? (
                <div className="space-y-3 rounded-xl border border-primary/40 bg-surface-container-lowest p-4">
                  <div className="space-y-2">
                    <label className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
                      Nombre del catálogo
                    </label>
                    <input
                      autoFocus
                      value={titleDraft}
                      onChange={(e) => setTitleDraft(e.target.value)}
                      className="w-full rounded-lg border border-outline-variant bg-surface px-3 py-2 text-headline-lg font-bold text-on-background outline-none focus:border-primary"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
                      Descripción
                    </label>
                    <textarea
                      rows={2}
                      value={summaryDraft}
                      onChange={(e) => setSummaryDraft(e.target.value)}
                      placeholder="Agregar descripción del catálogo…"
                      className="w-full resize-none rounded-lg border border-outline-variant bg-surface px-3 py-2 text-body-lg text-on-background outline-none focus:border-primary"
                    />
                  </div>
                  <div className="flex justify-end gap-3">
                    <button
                      onClick={() => setEditingMeta(false)}
                      disabled={savingMeta}
                      className="rounded-full border border-outline-variant px-5 py-2 font-mono text-label-md text-on-surface transition-colors hover:bg-surface-container-high disabled:opacity-40"
                    >
                      Cancelar
                    </button>
                    <button
                      onClick={saveMeta}
                      disabled={savingMeta || !titleDraft.trim()}
                      className="flex items-center gap-2 rounded-full bg-primary px-5 py-2 font-mono text-label-md text-on-primary shadow-md disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      <Icon name="save" className="text-[18px]" />
                      {savingMeta ? "Guardando…" : "Guardar"}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-start gap-3 sm:flex-row">
                  <div className="min-w-0 flex-1">
                    <h1 className="text-display-lg font-bold text-on-background wrap-break-word">
                      {job.plan?.catalog_title ?? "Catálogo"}
                    </h1>
                    {job.plan?.catalog_summary && (
                      <p className="text-body-lg text-on-surface-variant wrap-break-word">{job.plan.catalog_summary}</p>
                    )}
                  </div>
                  <button
                    onClick={startEditingMeta}
                    className="flex shrink-0 items-center gap-2 rounded-full border border-outline-variant px-4 py-2 font-mono text-label-sm text-on-surface transition-colors hover:bg-surface-container-high sm:mt-2"
                  >
                    <Icon name="edit" className="text-[16px]" />
                    Editar
                  </button>
                </div>
              )}
            </div>
            {publicUrl && (
              <div className="flex w-full flex-col gap-3 sm:w-auto sm:min-w-[320px]">
                <label className="pl-1 font-mono text-label-sm uppercase tracking-widest text-on-surface-variant">
                  Enlace público
                </label>
                <div className="flex items-center rounded-xl bg-surface-container-lowest p-1 shadow-sm">
                  <Icon name="link" className="px-3 text-outline" />
                  <input
                    readOnly
                    title={publicUrl}
                    value={`.../c/${jobId}`}
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
                    {/* {jsonUrl && (
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
                    )} */}
                    {pdfUrl && (
                      <a
                        href={pdfUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="group flex w-full items-center justify-between rounded-lg p-3 text-left transition-colors hover:bg-surface-container"
                      >
                        <div className="flex items-center gap-3">
                          <div className="flex h-8 w-8 items-center justify-center rounded bg-error-container text-on-error-container">
                            <Icon name="picture_as_pdf" className="text-sm" />
                          </div>
                          <span className="font-mono text-label-md text-on-background">Catálogo en PDF</span>
                        </div>
                        <Icon name="download" className="text-on-surface-variant opacity-0 transition-opacity group-hover:opacity-100" />
                      </a>
                    )}
                    <button
                      type="button"
                      onClick={downloadImagesZip}
                      disabled={downloadingImages}
                      className="group flex w-full items-center justify-between rounded-lg p-3 text-left transition-colors hover:bg-surface-container disabled:cursor-wait disabled:opacity-60"
                    >
                      <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded bg-surface-container-high text-on-surface">
                          <Icon name="folder_zip" className="text-sm" />
                        </div>
                        <span className="font-mono text-label-md text-on-background">
                          {downloadingImages ? "Preparando .zip…" : "Imágenes (.zip)"}
                        </span>
                      </div>
                      <Icon name="download" className="text-on-surface-variant opacity-0 transition-opacity group-hover:opacity-100" />
                    </button>
                    {downloadError && <ErrorBanner message={downloadError} className="mx-3" />}
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

                <div className="h-px w-full bg-surface-container-highest" />
                <button
                  type="button"
                  onClick={() => setPendingDeleteCatalog(true)}
                  className="flex w-full items-center justify-center gap-2 rounded-xl border border-error/30 py-3 font-mono text-label-md text-error transition-colors hover:bg-error hover:text-on-error"
                >
                  <Icon name="delete" className="text-[18px]" />
                  Eliminar catálogo
                </button>
              </div>
            </div>

            {/* Preview */}
            <div className="xl:col-span-9">
              <div
                className={`mx-auto rounded-2xl bg-surface-container-lowest p-8 shadow-xl ring-1 ring-surface-container-highest transition-all duration-500 md:p-12 ${
                  preview === "mobile" ? "max-w-sm rounded-[2.5rem]" : "max-w-none"
                }`}
              >
                <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center">
                  <div className="relative flex-1">
                    <Icon
                      name="search"
                      className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant"
                    />
                    <input
                      type="search"
                      value={searchQuery}
                      onChange={(e) => {
                        setSearchQuery(e.target.value);
                        resetPagination();
                      }}
                      placeholder="Buscar por nombre, marca, palabra clave…"
                      className="w-full rounded-full border border-outline-variant bg-surface py-2.5 pl-11 pr-4 text-body-md text-on-background outline-none transition-colors focus:border-primary"
                    />
                  </div>
                  <div className="flex shrink-0 gap-1 rounded-full bg-surface-container p-1">
                    {(
                      [
                        { key: "all", label: "Todos" },
                        { key: "visible", label: "Visibles" },
                        { key: "hidden", label: "Ocultos" },
                      ] as const
                    ).map((opt) => (
                      <button
                        key={opt.key}
                        onClick={() => {
                          setVisibilityFilter(opt.key);
                          resetPagination();
                        }}
                        className={`rounded-full px-4 py-1.5 font-mono text-label-sm transition-colors ${
                          visibilityFilter === opt.key
                            ? "bg-surface-container-lowest text-primary shadow-sm"
                            : "text-on-surface-variant hover:text-on-surface"
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <nav className="hide-scrollbar mb-8 -mx-4 flex gap-2 overflow-x-auto px-4 pb-4">
                  <button
                    onClick={() => {
                      setActiveCategory("Todos");
                      resetPagination();
                    }}
                    className={`whitespace-nowrap rounded-full px-6 py-2 font-mono text-label-md transition-colors ${
                      activeCategory === "Todos" ? "bg-primary text-on-primary shadow-md" : "bg-surface-container text-on-surface hover:bg-surface-container-high"
                    }`}
                  >
                    Todos
                  </button>
                  {categories.map((cat) => (
                    <button
                      key={cat}
                      onClick={() => {
                        setActiveCategory(cat);
                        resetPagination();
                      }}
                      className={`whitespace-nowrap rounded-full px-6 py-2 font-mono text-label-md transition-colors ${
                        activeCategory === cat ? "bg-primary text-on-primary shadow-md" : "bg-surface-container text-on-surface hover:bg-surface-container-high"
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </nav>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleFileSelected}
                  className="hidden"
                />

                {filteredProducts.length === 0 && (
                  <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-outline-variant py-16 text-center">
                    <Icon name="search_off" className="text-3xl text-on-surface-variant" />
                    <p className="text-body-md text-on-surface-variant">
                      Ningún producto coincide con la búsqueda o los filtros aplicados.
                    </p>
                  </div>
                )}

                <div className={`grid gap-6 ${preview === "mobile" ? "grid-cols-1" : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"}`}>
                  {visibleProducts.map((p) => {
                    const thumb = absoluteUrl(p.image.thumbnail_path ?? p.image.composed_path);
                    return (
                      <div
                        key={p.id}
                        role="button"
                        tabIndex={0}
                        onClick={() => setSelected(p)}
                        onKeyDown={(e) => e.key === "Enter" && setSelected(p)}
                        className={`group relative overflow-hidden rounded-2xl bg-surface text-left transition-all hover:-translate-y-1 hover:shadow-xl ${
                          p.visible ? "" : "opacity-50"
                        }`}
                      >
                        <div className="relative aspect-square overflow-hidden bg-surface-variant">
                          {thumb && (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={thumb} alt={p.sheet.name} className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105" />
                          )}
                          <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
                          {!p.visible && (
                            <span className="absolute left-3 top-3 flex items-center gap-1 rounded-full bg-inverse-surface/80 px-2.5 py-1 font-mono text-label-sm text-inverse-on-surface">
                              <Icon name="visibility_off" className="text-[16px]" />
                              Oculto
                            </span>
                          )}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setPendingDelete(p);
                            }}
                            title="Eliminar producto"
                            className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-full bg-surface/90 text-error shadow-sm backdrop-blur-md transition-colors hover:bg-error hover:text-on-error"
                          >
                            <Icon name="delete" className="text-[18px]" />
                          </button>
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
                      </div>
                    );
                  })}
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="flex aspect-square flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-outline-variant text-on-surface-variant transition-colors hover:border-primary hover:text-primary"
                  >
                    <Icon name="add_circle" className="text-4xl" />
                    <span className="font-mono text-label-md">Agregar producto</span>
                  </button>
                </div>

                {hasMoreProducts && (
                  <div className="mt-8 flex justify-center">
                    <button
                      onClick={() => setVisibleCount((count) => count + PRODUCTS_PAGE_SIZE)}
                      className="flex items-center gap-2 rounded-full border border-outline-variant px-6 py-2.5 font-mono text-label-md text-on-surface transition-colors hover:bg-surface-container-high"
                    >
                      Ver más ({filteredProducts.length - visibleProducts.length} restantes)
                      <Icon name="expand_more" className="text-[18px]" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      <Fab
        actions={[
          { label: "Añadir imagen", icon: "add_photo_alternate", onClick: () => fileInputRef.current?.click() },
        ]}
      />

      {selected && (
        <ProductEditModal
          jobId={jobId}
          product={selected}
          onSaved={(updated) => {
            mutate(updated);
            setSelected(updated.products.find((p) => p.id === selected.id) ?? null);
          }}
          onClose={() => setSelected(null)}
        />
      )}

      {pendingUpload && (
        <AddProductModal
          previewUrl={pendingUpload.previewUrl}
          uploadPromise={pendingUpload.uploadPromise}
          onAdded={(updated) => {
            mutate(updated);
            setActiveCategory("Todos");
            closePendingUpload();
          }}
          onClose={closePendingUpload}
        />
      )}

      {pendingDelete && (
        <ConfirmDialog
          title="Eliminar producto"
          message={`¿Eliminar "${pendingDelete.sheet.name}" del catálogo? Esta acción no se puede deshacer.`}
          confirmLabel="Eliminar"
          onConfirm={confirmDeleteProduct}
          onCancel={() => setPendingDelete(null)}
        />
      )}

      {pendingDeleteCatalog && (
        <ConfirmDialog
          title="Eliminar catálogo"
          message={`¿Eliminar "${job.plan?.catalog_title ?? job.id}"? Se borrarán las fotos, imágenes generadas y el catálogo publicado. Esta acción no se puede deshacer.`}
          confirmLabel={deletingCatalog ? "Eliminando…" : "Eliminar"}
          onConfirm={confirmDeleteCatalog}
          onCancel={() => setPendingDeleteCatalog(false)}
        />
      )}
    </AppShell>
  );
}
