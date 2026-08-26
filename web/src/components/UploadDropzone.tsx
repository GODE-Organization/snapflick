"use client";

import { useRef, useState } from "react";
import { Icon } from "./Icon";

export function UploadDropzone({
  files,
  onChange,
}: {
  files: File[];
  onChange: (files: File[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  function addFiles(list: FileList | null) {
    if (!list) return;
    onChange([...files, ...Array.from(list)]);
  }

  function removeAt(index: number) {
    onChange(files.filter((_, i) => i !== index));
  }

  return (
    <section className="rounded-xl bg-surface p-6 shadow-sm md:p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-headline-md font-semibold text-on-surface">Fotos de productos</h2>
          <p className="text-body-md text-on-surface-variant">Sube imágenes claras de tus artículos.</p>
        </div>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="flex items-center gap-2 rounded-lg bg-primary px-6 py-2 font-mono text-label-md text-on-primary shadow-md shadow-primary/20 transition-colors hover:bg-primary-container"
        >
          <Icon name="cloud_upload" className="text-[16px]" />
          Subir
        </button>
      </div>

      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          addFiles(e.dataTransfer.files);
        }}
        className={`group flex h-64 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed text-center transition-colors ${
          dragActive ? "border-primary bg-primary/5" : "border-outline-variant bg-surface-container-low hover:border-primary"
        }`}
      >
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-surface shadow-sm transition-transform duration-300 group-hover:scale-110">
          <Icon name="add_photo_alternate" className="text-3xl text-primary" />
        </div>
        <h3 className="mb-2 text-body-lg font-semibold text-on-surface">Arrastra y suelta aquí</h3>
        <p className="text-body-md text-on-surface-variant">o haz clic para explorar tus archivos (JPG, PNG)</p>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>

      {files.length === 0 ? (
        <div className="mt-4 flex items-start gap-3 rounded-lg bg-surface-container-lowest p-4">
          <Icon name="info" className="mt-0.5 text-electric-indigo" />
          <p className="text-body-md text-on-surface-variant">
            Aún no has subido fotos. Añade al menos una imagen para comenzar la generación del catálogo.
          </p>
        </div>
      ) : (
        <div className="mt-4">
          <p className="mb-2 font-mono text-label-sm text-on-surface-variant">
            {files.length} foto{files.length === 1 ? "" : "s"} seleccionada{files.length === 1 ? "" : "s"}
          </p>
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6">
            {files.map((file, i) => (
              <div key={`${file.name}-${i}`} className="group relative aspect-square overflow-hidden rounded-lg bg-surface-container-low">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={URL.createObjectURL(file)} alt={file.name} className="h-full w-full object-cover" />
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeAt(i);
                  }}
                  className="absolute right-1 top-1 grid h-6 w-6 place-items-center rounded-full bg-inverse-surface/70 text-inverse-on-surface opacity-0 transition group-hover:opacity-100"
                  aria-label={`Quitar ${file.name}`}
                >
                  <Icon name="close" className="text-[14px]" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
