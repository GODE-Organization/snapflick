"use client";

import { useRef, useState } from "react";
import { absoluteUrl, setDefaultBackground, uploadBackground } from "@/lib/api";
import { useBackgrounds } from "@/lib/hooks";
import { Icon } from "./Icon";

export type BackgroundChoice =
  | { mode: "none" }
  | { mode: "original" }
  | { mode: "saved"; key: string };

export function BackgroundPicker({
  value,
  onChange,
}: {
  value: BackgroundChoice;
  onChange: (choice: BackgroundChoice) => void;
}) {
  const { data: backgrounds, mutate } = useBackgrounds();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [settingDefault, setSettingDefault] = useState<string | null>(null);

  async function handleFiles(list: FileList | null) {
    if (!list || list.length === 0) return;
    setUploading(true);
    try {
      let last = null;
      for (const file of Array.from(list)) {
        last = await uploadBackground(file);
      }
      await mutate();
      if (last) onChange({ mode: "saved", key: last.background_key });
    } finally {
      setUploading(false);
    }
  }

  async function toggleDefault(bg: { background_key: string; is_default: boolean }) {
    setSettingDefault(bg.background_key);
    try {
      await setDefaultBackground(bg.is_default ? null : bg.background_key);
      await mutate();
    } finally {
      setSettingDefault(null);
    }
  }

  return (
    <section className="rounded-xl bg-surface p-6 shadow-sm md:p-8">
      <h2 className="mb-2 text-headline-md font-semibold text-on-surface">Fondo de marca</h2>
      <p className="mb-6 text-body-md text-on-surface-variant">
        Elige el fondo por defecto para el lote. Puedes subir varios y asignar uno distinto a cada
        foto más abajo. Marca una estrella para que ese fondo se use automáticamente en los
        próximos lotes.
      </p>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <button
          type="button"
          onClick={() => onChange({ mode: "none" })}
          className={`group relative flex aspect-square flex-col items-center justify-center gap-1 overflow-hidden rounded-lg bg-white shadow-sm ring-2 transition-colors ${
            value.mode === "none" ? "ring-primary" : "ring-transparent hover:ring-outline-variant"
          }`}
        >
          <Icon name="light_mode" className="text-2xl text-on-surface-variant" />
          <span className="font-mono text-label-sm text-on-surface-variant">Blanco</span>
          {value.mode === "none" && (
            <Icon name="check_circle" className="absolute right-1.5 top-1.5 text-primary" filled />
          )}
        </button>
        <button
          type="button"
          onClick={() => onChange({ mode: "original" })}
          className={`group relative flex aspect-square flex-col items-center justify-center gap-1 overflow-hidden rounded-lg bg-surface-container-high shadow-sm ring-2 transition-colors ${
            value.mode === "original" ? "ring-primary" : "ring-transparent hover:ring-outline-variant"
          }`}
        >
          <Icon name="image" className="text-2xl text-on-surface-variant" />
          <span className="px-1 text-center font-mono text-label-sm text-on-surface-variant">
            Mantener original
          </span>
          {value.mode === "original" && (
            <Icon name="check_circle" className="absolute right-1.5 top-1.5 text-primary" filled />
          )}
        </button>
        {backgrounds?.map((bg) => {
          const selected = value.mode === "saved" && value.key === bg.background_key;
          return (
            <div key={bg.background_key} className="group relative aspect-square overflow-hidden rounded-lg shadow-sm">
              <button
                type="button"
                onClick={() => onChange({ mode: "saved", key: bg.background_key })}
                className="h-full w-full cursor-pointer"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={absoluteUrl(bg.url) ?? undefined}
                  alt={bg.background_key}
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-110"
                />
                <div
                  className={`absolute inset-0 transition-colors ${selected ? "bg-primary/20" : "bg-surface/0 group-hover:bg-primary/20"}`}
                />
                {selected && (
                  <Icon name="check_circle" className="absolute bottom-2 right-2 text-white" filled />
                )}
              </button>
              <button
                type="button"
                title={bg.is_default ? "Quitar como fondo por defecto" : "Marcar como fondo por defecto"}
                disabled={settingDefault === bg.background_key}
                onClick={(e) => {
                  e.stopPropagation();
                  void toggleDefault(bg);
                }}
                className="absolute left-2 top-2 flex h-7 w-7 items-center justify-center rounded-full bg-surface/90 shadow-sm backdrop-blur-md transition-colors hover:bg-surface disabled:opacity-50"
              >
                <Icon
                  name="star"
                  className={`text-[16px] ${bg.is_default ? "text-vivid-cyan" : "text-on-surface-variant"}`}
                  filled={bg.is_default}
                />
              </button>
              {bg.is_default && (
                <span className="absolute bottom-2 left-2 rounded bg-surface/80 px-2 py-1 font-mono text-label-sm text-on-surface backdrop-blur-sm">
                  Por defecto
                </span>
              )}
            </div>
          );
        })}
        <button
          type="button"
          disabled={uploading}
          onClick={() => inputRef.current?.click()}
          className="flex aspect-square flex-col items-center justify-center gap-2 rounded-lg bg-surface-container-high text-on-surface-variant shadow-sm transition-colors hover:bg-surface-container-highest disabled:opacity-50"
        >
          <Icon name={uploading ? "hourglass_top" : "add"} className="text-3xl" />
          <span className="font-mono text-label-sm">{uploading ? "Subiendo…" : "Subir fondos"}</span>
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={(e) => {
            void handleFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </div>
    </section>
  );
}
