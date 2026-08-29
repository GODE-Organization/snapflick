"use client";

import { forwardRef, useImperativeHandle, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { Icon } from "@/components/Icon";
import { absoluteUrl, updateProduct } from "@/lib/api";
import { useJob } from "@/lib/hooks";
import type { Job, ProductRecord, ProductSheet } from "@/lib/types";

function ConfidenceDot({ level }: { level: ProductRecord["sheet"]["confidence"] }) {
  const color = level === "high" ? "bg-ai-success" : level === "medium" ? "bg-vivid-cyan" : "bg-error";
  const label =
    level === "high" ? "Confianza alta" : level === "medium" ? "Confianza media" : "Confianza baja — revisar";
  return <div className={`h-2 w-2 rounded-full ${color}`} title={label} />;
}

function EditableField({
  label,
  value,
  onChange,
  confidence,
  mono = false,
  textarea = false,
  placeholder = "No detectado",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  confidence?: ProductRecord["sheet"]["confidence"];
  mono?: boolean;
  textarea?: boolean;
  placeholder?: string;
}) {
  const sharedClassName = `w-full rounded-xl border border-transparent bg-surface-off-white px-4 py-3 text-body-md text-on-background outline-none transition-colors placeholder:text-on-surface-variant/50 focus:border-primary focus:bg-surface ${
    mono ? "font-mono" : ""
  } ${confidence ? "pr-10" : ""}`;

  return (
    <div className="flex flex-col gap-2">
      <label className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">{label}</label>
      <div className="relative">
        {textarea ? (
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            rows={3}
            className={`${sharedClassName} resize-none`}
          />
        ) : (
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            className={sharedClassName}
          />
        )}
        {confidence && (
          <div className="absolute right-3 top-3.5">
            <ConfidenceDot level={confidence} />
          </div>
        )}
      </div>
    </div>
  );
}

interface ProductEditorHandle {
  saveIfDirty: () => Promise<boolean>;
}

/**
 * Ficha editable de un producto. Se monta con `key={product.id}` desde el
 * padre, así que cuando el usuario cambia de producto React descarta y crea
 * una instancia nueva de este componente en vez de reutilizar la anterior —
 * el estado (`draft`, `keywordsInput`, …) nace ya sincronizado con
 * `product.sheet` sin necesitar un efecto que lo copie.
 */
const ProductEditor = forwardRef<
  ProductEditorHandle,
  { jobId: string; product: ProductRecord; onSaved: (job: Job) => void }
>(function ProductEditor({ jobId, product, onSaved }, ref) {
  const [draft, setDraft] = useState<ProductSheet>(product.sheet);
  const [keywordsInput, setKeywordsInput] = useState(product.sheet.keywords.join(", "));
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const dirty = useMemo(() => {
    const currentKeywords = product.sheet.keywords.join(", ");
    return (
      JSON.stringify({ ...draft, keywords: keywordsInput }) !==
      JSON.stringify({ ...product.sheet, keywords: currentKeywords })
    );
  }, [draft, keywordsInput, product.sheet]);

  function field<K extends keyof ProductSheet>(key: K, value: ProductSheet[K]) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  useImperativeHandle(ref, () => ({
    async saveIfDirty() {
      if (!dirty) return true;
      const finalSheet: ProductSheet = {
        ...draft,
        keywords: keywordsInput
          .split(",")
          .map((k) => k.trim())
          .filter(Boolean),
      };
      const patch: Partial<ProductSheet> = {};
      for (const key of Object.keys(finalSheet) as (keyof ProductSheet)[]) {
        if (JSON.stringify(finalSheet[key]) !== JSON.stringify(product.sheet[key])) {
          (patch as Record<string, unknown>)[key] = finalSheet[key];
        }
      }
      setSaving(true);
      setSaveError(null);
      try {
        const updated = await updateProduct(jobId, product.id, patch);
        onSaved(updated);
        return true;
      } catch {
        setSaveError("No se pudo guardar. Intenta de nuevo.");
        return false;
      } finally {
        setSaving(false);
      }
    },
  }));

  return (
    <div className="flex flex-col gap-8 rounded-[24px] border border-outline-variant/30 bg-surface-container-lowest p-8 shadow-sm">
      <div className="flex items-center justify-between border-b border-outline-variant/30 pb-6">
        <h2 className="text-headline-md font-semibold text-on-background">Ficha del producto</h2>
        <div className="flex items-center gap-3">
          {dirty && !saving && <span className="font-mono text-label-sm text-vivid-cyan">Cambios sin guardar</span>}
          {saving && <span className="font-mono text-label-sm text-on-surface-variant">Guardando…</span>}
          <span className="rounded-full bg-surface-container px-3 py-1 font-mono text-label-sm text-on-surface-variant">
            ID: {product.id}
          </span>
        </div>
      </div>

      {product.image.error && (
        <div className="flex items-center gap-2 rounded-lg bg-error-container p-4 text-on-error-container">
          <Icon name="error" />
          {product.image.error}
        </div>
      )}
      {saveError && (
        <div className="flex items-center gap-2 rounded-lg bg-error-container p-4 text-on-error-container">
          <Icon name="error" />
          {saveError}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <EditableField label="Nombre" value={draft.name} onChange={(v) => field("name", v)} confidence={product.sheet.confidence} />
        <EditableField
          label="Marca"
          value={draft.brand ?? ""}
          onChange={(v) => field("brand", v || null)}
          confidence={product.sheet.confidence}
        />
      </div>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <EditableField
          label="Presentación"
          value={draft.presentation ?? ""}
          onChange={(v) => field("presentation", v || null)}
        />
        <div className="md:col-span-2">
          <EditableField
            label="Categoría"
            value={draft.category ?? ""}
            onChange={(v) => field("category", v || null)}
            placeholder="Sin categoría"
            mono
          />
        </div>
      </div>
      <EditableField
        label="Descripción"
        value={draft.description}
        onChange={(v) => field("description", v)}
        confidence={product.sheet.confidence}
        textarea
      />
      <div className="flex flex-col gap-2">
        <label className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
          Palabras clave
        </label>
        <input
          type="text"
          value={keywordsInput}
          onChange={(e) => setKeywordsInput(e.target.value)}
          placeholder="separadas por coma"
          className="w-full rounded-xl border border-transparent bg-surface-off-white px-4 py-3 text-body-md text-on-background outline-none transition-colors placeholder:text-on-surface-variant/50 focus:border-primary focus:bg-surface"
        />
      </div>
      <EditableField label="Código de barras" value={draft.barcode ?? ""} onChange={(v) => field("barcode", v || null)} mono />
      <EditableField
        label="Notas"
        value={draft.notes ?? ""}
        onChange={(v) => field("notes", v || null)}
        placeholder="Sin notas"
        textarea
      />
    </div>
  );
});

export function ReviewClient({ jobId }: { jobId: string }) {
  const router = useRouter();
  const { data: job, error, mutate } = useJob(jobId);
  const [index, setIndex] = useState(0);
  const [imgTab, setImgTab] = useState<"composed" | "cutout" | "source">("composed");
  const editorRef = useRef<ProductEditorHandle>(null);

  const products = useMemo(() => job?.products ?? [], [job]);
  const current = products[index];

  async function goTo(nextIndex: number) {
    const ok = (await editorRef.current?.saveIfDirty()) ?? true;
    if (ok) {
      setIndex(nextIndex);
      setImgTab("composed");
    }
  }

  if (error) {
    return (
      <AppShell>
        <p className="p-8 text-body-md text-error">No se pudo cargar el lote.</p>
      </AppShell>
    );
  }
  if (!job || !current) {
    return (
      <AppShell>
        <p className="p-8 text-body-md text-on-surface-variant">Cargando…</p>
      </AppShell>
    );
  }

  const verified = products.filter((p) => p.sheet.confidence !== "low" && !p.image.error).length;
  const needsReview = products.length - verified;
  const jsonUrl = absoluteUrl(job.catalog_json_path);

  const images: { key: typeof imgTab; label: string; url: string | null }[] = [
    { key: "composed", label: "Compuesta", url: absoluteUrl(current.image.composed_path) },
    { key: "cutout", label: "Recorte", url: absoluteUrl(current.image.cutout_path) },
    { key: "source", label: "Original", url: absoluteUrl(current.image.source_path) },
  ];
  const mainImage = images.find((i) => i.key === imgTab)?.url ?? images[0].url;

  return (
    <AppShell>
      <div className="flex w-full flex-col pb-24">
        <div className="flex flex-col items-start justify-between gap-4 px-4 py-8 sm:px-margin-desktop md:flex-row md:items-center">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-container text-on-primary-container shadow-lg shadow-electric-indigo/20">
              <Icon name="fact_check" className="text-2xl" />
            </div>
            <div>
              <h1 className="text-headline-lg font-semibold tracking-tight text-on-background">Revisión de lote</h1>
              <p className="mt-1 text-body-md text-on-surface-variant">
                Lote {jobId} · {products.length} producto{products.length === 1 ? "" : "s"} procesado
                {products.length === 1 ? "" : "s"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {jsonUrl && (
              <a
                href={jsonUrl}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 rounded-full border border-outline-variant px-6 py-2.5 font-mono text-label-md text-on-surface transition-colors hover:bg-surface-container-high"
              >
                <Icon name="download" className="text-[20px]" />
                Exportar JSON
              </a>
            )}
            <Link
              href={`/jobs/${jobId}/catalog`}
              className="flex items-center gap-2 rounded-full bg-electric-indigo px-6 py-2.5 font-mono text-label-md text-on-primary shadow-glow transition-all"
            >
              <Icon name="rocket_launch" className="text-[20px]" />
              Ver catálogo
            </Link>
          </div>
        </div>

        <div className="flex gap-2 px-4 sm:px-margin-desktop">
          <span className="flex items-center gap-1 rounded-full bg-ai-success/10 px-3 py-1 font-mono text-label-sm text-ai-success">
            <Icon name="check_circle" className="text-[16px]" filled />
            {verified} verificados
          </span>
          {needsReview > 0 && (
            <span className="flex items-center gap-1 rounded-full bg-error/10 px-3 py-1 font-mono text-label-sm text-error">
              <Icon name="error" className="text-[16px]" filled />
              {needsReview} por revisar
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 gap-8 px-4 py-8 sm:px-margin-desktop xl:grid-cols-12">
          {/* Left: image */}
          <div className="flex flex-col gap-6 xl:col-span-5">
            <div className="relative overflow-hidden rounded-[24px] bg-surface-container p-6 shadow-sm">
              <div className="relative aspect-4/5 w-full overflow-hidden rounded-2xl bg-surface-container-high">
                {mainImage ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={mainImage} alt={current.sheet.name} className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full items-center justify-center text-on-surface-variant">Sin imagen</div>
                )}
                <div className="absolute left-4 top-4">
                  <span className="flex items-center gap-2 rounded-lg border border-outline-variant/50 bg-surface/90 px-3 py-1.5 font-mono text-label-sm text-on-surface shadow-sm backdrop-blur-md">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-vivid-cyan" />
                    Compuesta por IA
                  </span>
                </div>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              {images.map((img) => (
                <button
                  key={img.key}
                  disabled={!img.url}
                  onClick={() => setImgTab(img.key)}
                  className={`relative aspect-square overflow-hidden rounded-xl border-2 transition-opacity disabled:opacity-30 ${
                    imgTab === img.key ? "border-primary" : "border-outline-variant opacity-70 hover:opacity-100"
                  }`}
                >
                  {img.url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={img.url} alt={img.label} className="h-full w-full object-cover" />
                  ) : (
                    <div className="h-full w-full bg-surface-container-high" />
                  )}
                  <span className="absolute inset-x-0 bottom-0 bg-inverse-surface/70 py-0.5 text-center font-mono text-[10px] text-inverse-on-surface">
                    {img.label}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Right: data */}
          <div className="flex flex-col gap-6 xl:col-span-7">
            <ProductEditor key={current.id} ref={editorRef} jobId={jobId} product={current} onSaved={mutate} />

            <div className="mt-2 flex justify-end gap-4">
              <button
                onClick={() => goTo(Math.max(0, index - 1))}
                disabled={index === 0}
                className="rounded-full border border-outline-variant px-6 py-3 font-mono text-label-md text-on-surface transition-colors hover:bg-surface-container-high disabled:opacity-40"
              >
                Anterior
              </button>
              {index < products.length - 1 ? (
                <button
                  onClick={() => goTo(Math.min(products.length - 1, index + 1))}
                  className="flex items-center gap-2 rounded-full bg-primary px-8 py-3 font-mono text-label-md text-on-primary shadow-lg shadow-primary/20 transition-all hover:shadow-primary/40"
                >
                  <Icon name="check" className="text-[20px]" />
                  Siguiente producto
                </button>
              ) : (
                <button
                  onClick={async () => {
                    const ok = (await editorRef.current?.saveIfDirty()) ?? true;
                    if (ok) router.push(`/jobs/${jobId}/catalog`);
                  }}
                  className="flex items-center gap-2 rounded-full bg-primary px-8 py-3 font-mono text-label-md text-on-primary shadow-lg shadow-primary/20 transition-all hover:shadow-primary/40"
                >
                  <Icon name="rocket_launch" className="text-[20px]" />
                  Ir al catálogo
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Batch filmstrip */}
        <div className="mt-4 border-t border-outline-variant/30 px-4 pt-8 sm:px-margin-desktop">
          <h3 className="mb-6 font-mono text-sm uppercase tracking-widest text-on-surface-variant">
            Resumen del lote
          </h3>
          <div className="hide-scrollbar flex snap-x gap-4 overflow-x-auto pb-4">
            {products.map((p, i) => {
              const thumb = absoluteUrl(p.image.thumbnail_path ?? p.image.composed_path);
              const isCurrent = i === index;
              return (
                <button
                  key={p.id}
                  onClick={() => goTo(i)}
                  className={`relative aspect-square w-32 shrink-0 snap-start overflow-hidden rounded-xl ${
                    isCurrent
                      ? "ring-2 ring-primary"
                      : p.image.error
                        ? "ring-1 ring-error/50"
                        : ""
                  }`}
                >
                  {thumb ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={thumb} alt={p.sheet.name} className={`h-full w-full object-cover ${isCurrent ? "" : "opacity-70"}`} />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center bg-surface-container-high text-on-surface-variant">
                      <Icon name="error" className="text-error" />
                    </div>
                  )}
                  {p.image.error && <div className="absolute right-2 top-2 h-3 w-3 rounded-full bg-error" />}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
