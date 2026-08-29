"use client";

import { useRef } from "react";
import { absoluteUrl } from "@/lib/api";
import type { Job, ProductRecord } from "@/lib/types";
import { BeforeAfterSlider } from "./BeforeAfterSlider";
import { Icon } from "./Icon";
import { ProductEditor, type ProductEditorHandle } from "./ProductEditor";

export function ProductEditModal({
  jobId,
  product,
  onSaved,
  onClose,
}: {
  jobId: string;
  product: ProductRecord;
  onSaved: (job: Job) => void;
  onClose: () => void;
}) {
  const editorRef = useRef<ProductEditorHandle>(null);
  const before = absoluteUrl(product.image.source_path);
  const after = absoluteUrl(product.image.composed_path);

  async function handleClose() {
    await editorRef.current?.saveIfDirty();
    onClose();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-inverse-surface/40 p-4"
      onClick={handleClose}
    >
      <div
        className="glass max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-[24px] border border-outline-variant/40 p-8 shadow-glow"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-6 flex items-start justify-between gap-4 border-b border-outline-variant/30 pb-6">
          <h2 className="text-headline-md font-semibold text-on-surface">{product.sheet.name}</h2>
          <button
            onClick={handleClose}
            className="flex shrink-0 items-center gap-1 rounded-full border border-outline-variant px-4 py-2 font-mono text-label-sm text-on-surface transition-colors hover:bg-surface-container-high"
          >
            <Icon name="close" className="text-[16px]" />
            Cerrar
          </button>
        </div>

        <div className="grid gap-6 sm:grid-cols-5">
          <div className="sm:col-span-2">
            {before && after ? (
              <BeforeAfterSlider beforeUrl={before} afterUrl={after} alt={product.sheet.name} />
            ) : (
              <p className="text-body-md text-on-surface-variant">Imágenes no disponibles.</p>
            )}
          </div>
          <div className="sm:col-span-3">
            <ProductEditor key={product.id} ref={editorRef} jobId={jobId} product={product} onSaved={onSaved} />
          </div>
        </div>
      </div>
    </div>
  );
}
