"use client";

import { useRef } from "react";
import { absoluteUrl } from "@/lib/api";
import { useBackgrounds } from "@/lib/hooks";
import { Icon } from "./Icon";

export type BackgroundChoice =
  | { mode: "none" }
  | { mode: "upload"; file: File }
  | { mode: "saved"; key: string };

export function BackgroundPicker({
  value,
  onChange,
}: {
  value: BackgroundChoice;
  onChange: (choice: BackgroundChoice) => void;
}) {
  const { data: backgrounds } = useBackgrounds();
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <section className="rounded-xl bg-surface p-6 shadow-sm md:p-8">
      <h2 className="mb-2 text-headline-md font-semibold text-on-surface">Fondo de marca</h2>
      <p className="mb-6 text-body-md text-on-surface-variant">
        Elige el ambiente en el que se integrarán tus productos. Opcional.
      </p>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {backgrounds?.map((bg) => {
          const selected = value.mode === "saved" && value.key === bg.background_key;
          return (
            <button
              key={bg.background_key}
              type="button"
              onClick={() => onChange({ mode: "saved", key: bg.background_key })}
              className="group relative aspect-square cursor-pointer overflow-hidden rounded-lg shadow-sm"
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
              <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between">
                <span className="rounded bg-surface/80 px-2 py-1 font-mono text-label-sm text-on-surface backdrop-blur-sm">
                  Guardado
                </span>
                {selected && <Icon name="check_circle" className="text-white" filled />}
              </div>
            </button>
          );
        })}
        {value.mode === "upload" && (
          <div className="group relative aspect-square overflow-hidden rounded-lg shadow-sm ring-2 ring-primary">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={URL.createObjectURL(value.file)} alt="Fondo subido" className="h-full w-full object-cover" />
            <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between">
              <span className="rounded bg-surface/80 px-2 py-1 font-mono text-label-sm text-on-surface backdrop-blur-sm">
                Nuevo
              </span>
              <Icon name="check_circle" className="text-primary" filled />
            </div>
          </div>
        )}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="flex aspect-square flex-col items-center justify-center gap-2 rounded-lg bg-surface-container-high text-on-surface-variant shadow-sm transition-colors hover:bg-surface-container-highest"
        >
          <Icon name="add" className="text-3xl" />
          <span className="font-mono text-label-sm">Subir fondo</span>
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            onChange(file ? { mode: "upload", file } : { mode: "none" });
          }}
        />
      </div>
    </section>
  );
}
