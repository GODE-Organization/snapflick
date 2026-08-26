"use client";

import { absoluteUrl } from "@/lib/api";
import type { ProductRecord } from "@/lib/types";
import { BeforeAfterSlider } from "./BeforeAfterSlider";
import { Icon } from "./Icon";

export function ProductDetailModal({
  product,
  onClose,
}: {
  product: ProductRecord;
  onClose: () => void;
}) {
  const before = absoluteUrl(product.image.source_path);
  const after = absoluteUrl(product.image.composed_path);
  const { sheet } = product;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-inverse-surface/40 p-4"
      onClick={onClose}
    >
      <div
        className="glass max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-[24px] border border-outline-variant/40 p-8 shadow-glow"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-6 flex items-start justify-between gap-4 border-b border-outline-variant/30 pb-6">
          <div>
            <h2 className="text-headline-md font-semibold text-on-surface">{sheet.name}</h2>
            {sheet.brand && <p className="text-body-md text-on-surface-variant">{sheet.brand}</p>}
          </div>
          <button
            onClick={onClose}
            className="flex items-center gap-1 rounded-full border border-outline-variant px-4 py-2 font-mono text-label-sm text-on-surface transition-colors hover:bg-surface-container-high"
          >
            <Icon name="close" className="text-[16px]" />
            Cerrar
          </button>
        </div>

        <div className="grid gap-6 sm:grid-cols-2">
          <div>
            {before && after ? (
              <BeforeAfterSlider beforeUrl={before} afterUrl={after} alt={sheet.name} />
            ) : (
              <p className="text-body-md text-on-surface-variant">Imágenes no disponibles.</p>
            )}
          </div>

          <dl className="flex flex-col gap-3 text-body-md">
            {sheet.presentation && (
              <div>
                <dt className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">Presentación</dt>
                <dd>{sheet.presentation}</dd>
              </div>
            )}
            <div>
              <dt className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">Descripción</dt>
              <dd>{sheet.description}</dd>
            </div>
            {sheet.category && (
              <div>
                <dt className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">Categoría</dt>
                <dd>{sheet.category}</dd>
              </div>
            )}
            {sheet.keywords.length > 0 && (
              <div>
                <dt className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">Palabras clave</dt>
                <dd className="flex flex-wrap gap-1">
                  {sheet.keywords.map((k) => (
                    <span key={k} className="rounded-full bg-surface-container px-2 py-0.5 text-label-sm">
                      {k}
                    </span>
                  ))}
                </dd>
              </div>
            )}
            {sheet.barcode && (
              <div>
                <dt className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">Código de barras</dt>
                <dd className="font-mono">{sheet.barcode}</dd>
              </div>
            )}
            <div>
              <dt className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">Confianza de extracción</dt>
              <dd className="capitalize">{sheet.confidence}</dd>
            </div>
            {sheet.notes && (
              <div>
                <dt className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">Notas</dt>
                <dd className="text-on-surface-variant italic">{sheet.notes}</dd>
              </div>
            )}
            {product.image.error && (
              <div className="rounded-md bg-error-container p-2 text-on-error-container">
                {product.image.error}
              </div>
            )}
          </dl>
        </div>
      </div>
    </div>
  );
}
