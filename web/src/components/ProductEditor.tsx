"use client";

import { forwardRef, useImperativeHandle, useMemo, useState } from "react";
import { absoluteUrl, KEEP_ORIGINAL_BACKGROUND, updateProduct, updateProductBackground } from "@/lib/api";
import { useBackgrounds } from "@/lib/hooks";
import type { Job, ProductRecord, ProductSheet } from "@/lib/types";
import { Icon } from "./Icon";

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

export interface ProductEditorHandle {
  saveIfDirty: () => Promise<boolean>;
}

/**
 * Ficha editable de un producto. Se monta con `key={product.id}` desde el
 * padre, así que cuando el usuario cambia de producto React descarta y crea
 * una instancia nueva de este componente en vez de reutilizar la anterior —
 * el estado (`draft`, `keywordsInput`, …) nace ya sincronizado con
 * `product.sheet` sin necesitar un efecto que lo copie.
 *
 * Se usa tanto en la vista de revisión (`ReviewClient`) como en el catálogo
 * ya publicado (`CatalogClient`): editar un producto no debería depender de
 * en qué paso del flujo esté el usuario.
 */
export const ProductEditor = forwardRef<
  ProductEditorHandle,
  { jobId: string; product: ProductRecord; onSaved: (job: Job) => void }
>(function ProductEditor({ jobId, product, onSaved }, ref) {
  const [draft, setDraft] = useState<ProductSheet>(product.sheet);
  const [keywordsInput, setKeywordsInput] = useState(product.sheet.keywords.join(", "));
  const [visible, setVisible] = useState(product.visible);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const { data: backgrounds } = useBackgrounds();
  const [changingBackground, setChangingBackground] = useState(false);
  const [backgroundError, setBackgroundError] = useState<string | null>(null);

  async function changeBackground(key: string | null) {
    setChangingBackground(true);
    setBackgroundError(null);
    try {
      const updated = await updateProductBackground(jobId, product.id, key);
      onSaved(updated);
    } catch {
      setBackgroundError("No se pudo cambiar el fondo. Intenta de nuevo.");
    } finally {
      setChangingBackground(false);
    }
  }

  const dirty = useMemo(() => {
    const currentKeywords = product.sheet.keywords.join(", ");
    const sheetDirty =
      JSON.stringify({ ...draft, keywords: keywordsInput }) !==
      JSON.stringify({ ...product.sheet, keywords: currentKeywords });
    return sheetDirty || visible !== product.visible;
  }, [draft, keywordsInput, visible, product.sheet, product.visible]);

  function field<K extends keyof ProductSheet>(key: K, value: ProductSheet[K]) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  async function save(): Promise<boolean> {
    if (!dirty) return true;
    const finalSheet: ProductSheet = {
      ...draft,
      keywords: keywordsInput
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean),
    };
    const patch: Partial<ProductSheet> & { visible?: boolean } = {};
    for (const key of Object.keys(finalSheet) as (keyof ProductSheet)[]) {
      if (JSON.stringify(finalSheet[key]) !== JSON.stringify(product.sheet[key])) {
        (patch as Record<string, unknown>)[key] = finalSheet[key];
      }
    }
    if (visible !== product.visible) patch.visible = visible;
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
  }

  useImperativeHandle(ref, () => ({ saveIfDirty: save }));

  return (
    <div className="flex flex-col gap-8 rounded-[24px] border border-outline-variant/30 bg-surface-container-lowest p-8 shadow-sm">
      <div className="flex items-center justify-between border-b border-outline-variant/30 pb-6">
        <h2 className="text-headline-md font-semibold text-on-background">Ficha del producto</h2>
        <span className="shrink-0 rounded-full bg-surface-container px-3 py-1 font-mono text-label-sm text-on-surface-variant">
          ID: {product.id}
        </span>
      </div>

      <div className="flex items-center gap-2 rounded-lg bg-primary-container p-4 text-on-primary-container">
        <Icon name="info" />
        Estás editando los detalles del producto
      </div>

      <div className="flex items-center justify-between gap-3 rounded-lg bg-surface-container p-4">
        <div className="flex min-w-0 items-center gap-2">
          <Icon name={visible ? "visibility" : "visibility_off"} className="shrink-0 text-on-surface-variant" />
          <div className="min-w-0">
            <p className="text-body-md text-on-background">Visible en el catálogo</p>
            <p className="text-body-sm text-on-surface-variant">
              {visible ? "Los clientes pueden ver este producto." : "Oculto: no aparece en el catálogo publicado."}
            </p>
          </div>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={visible}
          onClick={() => setVisible((v) => !v)}
          className={`inline-flex h-7 w-12 shrink-0 items-center rounded-full p-0.5 transition-colors ${visible ? "bg-primary" : "bg-outline-variant"}`}
        >
          <span
            className={`h-6 w-6 rounded-full bg-surface shadow-md transition-transform ${
              visible ? "translate-x-5" : "translate-x-0"
            }`}
          />
        </button>
      </div>

      <div className="flex flex-col gap-3 rounded-lg bg-surface-container p-4">
        <div className="flex items-center gap-2">
          <Icon name="wallpaper" className="text-on-surface-variant" />
          <p className="text-body-md text-on-background">Fondo del producto</p>
          {changingBackground && (
            <span className="font-mono text-label-sm text-on-surface-variant">Aplicando…</span>
          )}
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            disabled={changingBackground}
            onClick={() => void changeBackground(null)}
            className={`flex h-16 w-16 shrink-0 items-center justify-center rounded-lg border-2 bg-white text-label-sm font-mono text-on-surface-variant transition-colors disabled:opacity-50 ${
              product.background_key === null ? "border-primary" : "border-transparent"
            }`}
            title="Fondo blanco"
          >
            Blanco
          </button>
          <button
            type="button"
            disabled={changingBackground}
            onClick={() => void changeBackground(KEEP_ORIGINAL_BACKGROUND)}
            className={`flex h-16 w-16 shrink-0 flex-col items-center justify-center gap-1 rounded-lg border-2 bg-surface-container-high px-1 text-center text-label-sm font-mono text-on-surface-variant transition-colors disabled:opacity-50 ${
              product.background_key === KEEP_ORIGINAL_BACKGROUND ? "border-primary" : "border-transparent"
            }`}
            title="Mantener el fondo original de la foto"
          >
            <Icon name="image" className="text-[18px]" />
            Original
          </button>
          {backgrounds?.map((bg) => {
            const selected = product.background_key === bg.url;
            return (
              <button
                key={bg.background_key}
                type="button"
                disabled={changingBackground}
                onClick={() => void changeBackground(bg.background_key)}
                className={`relative h-16 w-16 shrink-0 overflow-hidden rounded-lg border-2 transition-colors disabled:opacity-50 ${
                  selected ? "border-primary" : "border-transparent"
                }`}
                title={bg.background_key}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={absoluteUrl(bg.url) ?? undefined} alt={bg.background_key} className="h-full w-full object-cover" />
                {selected && (
                  <div className="absolute inset-0 flex items-center justify-center bg-primary/20">
                    <Icon name="check_circle" className="text-white" filled />
                  </div>
                )}
                {bg.is_default && (
                  <Icon name="star" className="absolute left-1 top-1 text-[14px] text-vivid-cyan" filled />
                )}
              </button>
            );
          })}
        </div>
      </div>
      {backgroundError && (
        <div className="flex items-center gap-2 rounded-lg bg-error-container p-4 text-on-error-container">
          <Icon name="error" />
          {backgroundError}
        </div>
      )}

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
        <p className="text-body-sm text-on-surface-variant">Ayudan a que el producto aparezca en búsquedas del catálogo.</p>
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

      <div className="flex items-center justify-end gap-3 border-t border-outline-variant/30 pt-6">
        {dirty && !saving && <span className="font-mono text-label-sm text-vivid-cyan">Cambios sin guardar</span>}
        <button
          onClick={() => void save()}
          disabled={!dirty || saving}
          className="flex items-center gap-2 rounded-full bg-primary px-6 py-2.5 font-mono text-label-md text-on-primary shadow-md transition-all disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Icon name="save" className="text-[18px]" />
          {saving ? "Guardando…" : "Guardar cambios"}
        </button>
      </div>
    </div>
  );
});
