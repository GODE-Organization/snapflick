"use client";

import { useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ErrorBanner } from "@/components/ErrorState";
import { Icon } from "@/components/Icon";
import { LoadingState } from "@/components/LoadingState";
import { useToast } from "@/components/Toast";
import { updateAgentSettings } from "@/lib/api";
import { useAgentSettings } from "@/lib/hooks";
import type { AgentSettings } from "@/lib/types";

function RulesField({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-[24px] border border-outline-variant/30 bg-surface-container-lowest p-8 shadow-sm">
      <label className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
        {label}
      </label>
      <p className="text-body-sm text-on-surface-variant">{hint}</p>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Sin reglas adicionales"
        rows={6}
        maxLength={1000}
        className="w-full resize-none rounded-xl border border-transparent bg-surface-off-white px-4 py-3 text-body-md text-on-background outline-none transition-colors placeholder:text-on-surface-variant/50 focus:border-primary focus:bg-surface"
      />
    </div>
  );
}

/**
 * `key={JSON.stringify(settings)}`-free equivalent de `ProductEditor`: se monta una sola
 * vez con `settings` ya cargado (ver `AjustesIaPage`), así que `draft` nace sincronizado
 * sin necesitar un efecto que lo copie desde el resultado de SWR.
 */
function SettingsForm({
  settings,
  onSaved,
}: {
  settings: AgentSettings;
  onSaved: (settings: AgentSettings) => void;
}) {
  const [draft, setDraft] = useState<AgentSettings>(settings);
  const [saving, setSaving] = useState(false);
  const toast = useToast();

  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(settings), [draft, settings]);

  async function save() {
    if (!dirty) return;
    setSaving(true);
    try {
      const updated = await updateAgentSettings(draft);
      onSaved(updated);
      toast.success("Reglas guardadas.");
    } catch {
      toast.error("No se pudieron guardar las reglas. Intenta de nuevo.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <RulesField
          label="Descripciones de producto"
          hint="Se aplican al leer cada foto y redactar la ficha (nombre, descripción, palabras clave)."
          value={draft.product_rules}
          onChange={(v) => setDraft({ ...draft, product_rules: v })}
        />
        <RulesField
          label="Catálogo"
          hint="Se aplican una vez por lote, al decidir categorías, título y resumen del catálogo."
          value={draft.catalog_rules}
          onChange={(v) => setDraft({ ...draft, catalog_rules: v })}
        />
      </div>

      <div className="flex items-center justify-end gap-3">
        {dirty && !saving && (
          <span className="font-mono text-label-sm text-vivid-cyan">Cambios sin guardar</span>
        )}
        <button
          onClick={() => void save()}
          disabled={!dirty || saving}
          className="flex items-center gap-2 rounded-full bg-primary px-6 py-2.5 font-mono text-label-md text-on-primary shadow-md transition-all disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Icon name="save" className="text-[18px]" />
          {saving ? "Guardando…" : "Guardar cambios"}
        </button>
      </div>
    </>
  );
}

export default function AjustesIaPage() {
  const { data: settings, error, mutate } = useAgentSettings();

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-(--container-max) space-y-8 px-4 py-12 sm:px-margin-desktop md:py-16">
        <div>
          <h1 className="text-display-sm font-bold text-on-surface">Configuración del agente</h1>
          <p className="mt-1 text-body-md text-on-surface-variant">
            Reglas propias que el agente sigue al redactar descripciones de producto y al armar
            el catálogo — tono, qué evitar, cómo agrupar categorías, etc.
          </p>
          <p className="mt-1 text-body-sm text-on-surface-variant/70">
            Solo se aplican reglas sobre el catálogo, los productos, las imágenes o las
            descripciones — el agente ignora cualquier instrucción que se salga de ese ámbito.
          </p>
        </div>

        {error ? (
          <ErrorBanner message="No se pudo cargar la configuración. Intenta de nuevo." />
        ) : !settings ? (
          <LoadingState compact title="Cargando…" />
        ) : (
          <SettingsForm settings={settings} onSaved={(updated) => void mutate(updated)} />
        )}
      </div>
    </AppShell>
  );
}
