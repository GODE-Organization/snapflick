"use client";

import { absoluteUrl, EXPLICIT_WHITE_BACKGROUND, KEEP_ORIGINAL_BACKGROUND } from "@/lib/api";
import type { BackgroundOption } from "@/lib/types";
import { Icon } from "./Icon";

/** Modal para elegir el fondo de marca de una foto puntual, a partir de los
 * fondos ya guardados — reemplaza el `<select>` nativo (poco amigable, sobre
 * todo con nombres de archivo largos) por una grilla de miniaturas, con el
 * mismo estilo que el resto de los modales (glass, rounded-[24px], shadow-glow). */
export function BackgroundPickerModal({
  backgrounds,
  selected,
  onSelect,
  onClose,
}: {
  backgrounds: BackgroundOption[];
  selected: string | null;
  onSelect: (key: string | null) => void;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-inverse-surface/40 p-4"
      onClick={onClose}
    >
      <div
        className="glass w-full max-w-lg rounded-[24px] border border-outline-variant/40 p-8 shadow-glow"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-headline-md font-semibold text-on-surface">Elegir fondo</h2>
            <p className="text-body-sm text-on-surface-variant">Se usará solo para esta foto.</p>
          </div>
          <button
            onClick={onClose}
            className="flex shrink-0 items-center gap-1 rounded-full border border-outline-variant px-4 py-2 font-mono text-label-sm text-on-surface transition-colors hover:bg-surface-container-high"
          >
            <Icon name="close" className="text-[16px]" />
            Cerrar
          </button>
        </div>

        <div className="grid grid-cols-3 gap-4 sm:grid-cols-4">
          <button
            type="button"
            onClick={() => {
              onSelect(null);
              onClose();
            }}
            className={`group relative flex aspect-square flex-col items-center justify-center gap-1 overflow-hidden rounded-lg bg-surface-container-high shadow-sm ring-2 transition-colors ${
              selected === null ? "ring-primary" : "ring-transparent hover:ring-outline-variant"
            }`}
          >
            <Icon name="auto_awesome" className="text-2xl text-on-surface-variant" />
            <span className="px-1 text-center font-mono text-label-sm text-on-surface-variant">
              Fondo por defecto
            </span>
            {selected === null && (
              <Icon name="check_circle" className="absolute right-1.5 top-1.5 text-primary" filled />
            )}
          </button>
          <button
            type="button"
            onClick={() => {
              onSelect(EXPLICIT_WHITE_BACKGROUND);
              onClose();
            }}
            className={`group relative flex aspect-square flex-col items-center justify-center gap-1 overflow-hidden rounded-lg bg-white shadow-sm ring-2 transition-colors ${
              selected === EXPLICIT_WHITE_BACKGROUND ? "ring-primary" : "ring-transparent hover:ring-outline-variant"
            }`}
          >
            <Icon name="light_mode" className="text-2xl text-on-surface-variant" />
            <span className="font-mono text-label-sm text-on-surface-variant">Blanco</span>
            {selected === EXPLICIT_WHITE_BACKGROUND && (
              <Icon name="check_circle" className="absolute right-1.5 top-1.5 text-primary" filled />
            )}
          </button>
          <button
            type="button"
            onClick={() => {
              onSelect(KEEP_ORIGINAL_BACKGROUND);
              onClose();
            }}
            className={`group relative flex aspect-square flex-col items-center justify-center gap-1 overflow-hidden rounded-lg bg-surface-container-high shadow-sm ring-2 transition-colors ${
              selected === KEEP_ORIGINAL_BACKGROUND ? "ring-primary" : "ring-transparent hover:ring-outline-variant"
            }`}
          >
            <Icon name="image" className="text-2xl text-on-surface-variant" />
            <span className="px-1 text-center font-mono text-label-sm text-on-surface-variant">
              Mantener original
            </span>
            {selected === KEEP_ORIGINAL_BACKGROUND && (
              <Icon name="check_circle" className="absolute right-1.5 top-1.5 text-primary" filled />
            )}
          </button>
          {backgrounds.map((bg) => {
            const isSelected = selected === bg.background_key;
            return (
              <button
                key={bg.background_key}
                type="button"
                onClick={() => {
                  onSelect(bg.background_key);
                  onClose();
                }}
                className={`group relative aspect-square overflow-hidden rounded-lg shadow-sm ring-2 transition-colors ${
                  isSelected ? "ring-primary" : "ring-transparent hover:ring-outline-variant"
                }`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={absoluteUrl(bg.url) ?? undefined}
                  alt={bg.background_key}
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-110"
                />
                {isSelected && (
                  <div className="absolute inset-0 flex items-center justify-center bg-primary/20">
                    <Icon name="check_circle" className="text-white" filled />
                  </div>
                )}
                {bg.is_default && (
                  <Icon
                    name="star"
                    className="absolute left-1.5 top-1.5 text-[16px] text-vivid-cyan"
                    filled
                  />
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
