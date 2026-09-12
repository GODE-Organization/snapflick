"use client";

import { useState } from "react";
import { absoluteUrl } from "@/lib/api";
import { usePublicCatalog } from "@/lib/hooks";
import type { PublicCatalogProduct } from "@/lib/types";
import { ErrorState } from "@/components/ErrorState";
import { Icon } from "@/components/Icon";
import { LoadingState } from "@/components/LoadingState";
import { Logo } from "@/components/Logo";

function ProductLightbox({ product, onClose }: { product: PublicCatalogProduct; onClose: () => void }) {
  const image = absoluteUrl(product.image_url);
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-inverse-surface/40 p-4"
      onClick={onClose}
    >
      <div
        className="glass max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-[24px] border border-outline-variant/40 p-8 shadow-glow"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-6 flex items-start justify-between gap-4 border-b border-outline-variant/30 pb-6">
          <h2 className="text-headline-md font-semibold text-on-surface">{product.name}</h2>
          <button
            onClick={onClose}
            className="flex shrink-0 items-center gap-1 rounded-full border border-outline-variant px-4 py-2 font-mono text-label-sm text-on-surface transition-colors hover:bg-surface-container-high"
          >
            <Icon name="close" className="text-[16px]" />
            Cerrar
          </button>
        </div>
        <div className="grid gap-6 sm:grid-cols-2">
          <div className="aspect-square overflow-hidden rounded-2xl bg-surface-variant">
            {image && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={image} alt={product.name} className="h-full w-full object-cover" />
            )}
          </div>
          <div className="space-y-4">
            {product.category && (
              <span className="inline-block rounded bg-primary/10 px-2 py-1 font-mono text-label-sm text-primary">
                {product.category}
              </span>
            )}
            <div>
              {product.brand && <p className="font-mono text-label-md text-on-surface-variant">{product.brand}</p>}
              {product.presentation && (
                <p className="font-mono text-label-sm text-on-surface-variant opacity-80">{product.presentation}</p>
              )}
            </div>
            <p className="text-body-md text-on-background">{product.description}</p>
            {product.keywords.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {product.keywords.map((k) => (
                  <span
                    key={k}
                    className="rounded-full bg-surface-container-high px-3 py-1 font-mono text-label-sm text-on-surface-variant"
                  >
                    {k}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function PublicHeader() {
  return (
    <header className="w-full border-b border-outline-variant bg-surface/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 w-full max-w-(--container-max) items-center px-4 sm:px-margin-desktop">
        <Logo />
      </div>
    </header>
  );
}

export function PublicCatalogClient({ jobId }: { jobId: string }) {
  const { data: catalog, error } = usePublicCatalog(jobId);
  const [activeCategory, setActiveCategory] = useState<string>("Todos");
  const [searchQuery, setSearchQuery] = useState("");
  const [selected, setSelected] = useState<PublicCatalogProduct | null>(null);

  if (error) {
    return (
      <>
        <PublicHeader />
        <ErrorState
          icon="link_off"
          title="Catálogo no disponible"
          message="Este catálogo no existe o ya no está disponible."
          actionHref="/"
          actionLabel="Ir a SnapFlick"
        />
      </>
    );
  }

  if (!catalog) {
    return (
      <>
        <PublicHeader />
        <LoadingState title="Cargando catálogo…" />
      </>
    );
  }

  const normalizedQuery = searchQuery.trim().toLowerCase();
  const filteredProducts = catalog.products.filter((p) => {
    const matchesCategory = activeCategory === "Todos" || p.category === activeCategory;
    const matchesSearch =
      !normalizedQuery ||
      [p.name, p.brand, p.presentation, p.description, ...p.keywords]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery);
    return matchesCategory && matchesSearch;
  });

  return (
    <>
      <PublicHeader />
      <div className="relative w-full">
        <div
          aria-hidden
          className="pointer-events-none fixed -z-10 h-full w-full bg-gradient-to-br from-background via-surface-container-low to-background"
        />
        <div className="mx-auto w-full max-w-(--container-max) space-y-8 px-4 py-12 sm:px-margin-desktop">
          <div className="space-y-2">
            <h1 className="text-display-lg font-bold text-on-background wrap-break-word">{catalog.catalog_title}</h1>
            {catalog.catalog_summary && (
              <p className="text-body-lg text-on-surface-variant wrap-break-word">{catalog.catalog_summary}</p>
            )}
          </div>

          <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Icon
                name="search"
                className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant"
              />
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Buscar por nombre, marca, palabra clave…"
                className="w-full rounded-full border border-outline-variant bg-surface py-2.5 pl-11 pr-4 text-body-md text-on-background outline-none transition-colors focus:border-primary"
              />
            </div>
          </div>

          <nav className="hide-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4 pb-2">
            <button
              onClick={() => setActiveCategory("Todos")}
              className={`whitespace-nowrap rounded-full px-6 py-2 font-mono text-label-md transition-colors ${
                activeCategory === "Todos"
                  ? "bg-primary text-on-primary shadow-md"
                  : "bg-surface-container text-on-surface hover:bg-surface-container-high"
              }`}
            >
              Todos
            </button>
            {catalog.categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className={`whitespace-nowrap rounded-full px-6 py-2 font-mono text-label-md transition-colors ${
                  activeCategory === cat
                    ? "bg-primary text-on-primary shadow-md"
                    : "bg-surface-container text-on-surface hover:bg-surface-container-high"
                }`}
              >
                {cat}
              </button>
            ))}
          </nav>

          {filteredProducts.length === 0 && (
            <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-outline-variant py-16 text-center">
              <Icon name="search_off" className="text-3xl text-on-surface-variant" />
              <p className="text-body-md text-on-surface-variant">
                Ningún producto coincide con la búsqueda o los filtros aplicados.
              </p>
            </div>
          )}

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filteredProducts.map((p) => {
              const thumb = absoluteUrl(p.image_url);
              return (
                <div
                  key={p.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelected(p)}
                  onKeyDown={(e) => e.key === "Enter" && setSelected(p)}
                  className="group relative overflow-hidden rounded-2xl bg-surface text-left transition-all hover:-translate-y-1 hover:shadow-xl"
                >
                  <div className="relative aspect-square overflow-hidden bg-surface-variant">
                    {thumb && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={thumb}
                        alt={p.name}
                        className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
                      />
                    )}
                    <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
                  </div>
                  <div className="p-5">
                    <h4 className="mb-2 line-clamp-1 text-headline-md font-semibold text-on-background">{p.name}</h4>
                    {p.category && (
                      <span className="mb-2 inline-block rounded bg-primary/10 px-2 py-1 font-mono text-label-sm text-primary">
                        {p.category}
                      </span>
                    )}
                    {(p.brand || p.presentation) && (
                      <p className="mb-1 font-mono text-label-sm text-on-surface-variant">
                        {[p.brand, p.presentation].filter(Boolean).join(" · ")}
                      </p>
                    )}
                    <p className="line-clamp-2 text-body-md text-on-surface-variant">{p.description}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {selected && <ProductLightbox product={selected} onClose={() => setSelected(null)} />}
    </>
  );
}
