"use client";

import { useEffect } from "react";
import { ErrorState } from "@/components/ErrorState";
// global-error replaces the root layout entirely, so global styles (Tailwind,
// CSS variables like --color-error) don't reach it unless imported here too.
import "./globals.css";

/** Se activa solo si el root layout mismo falla al renderizar — por eso
 * define su propio <html>/<body> en vez de envolver con AppShell/layout.tsx. */
export default function GlobalError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="es">
      <body className="flex min-h-screen items-center justify-center bg-surface-off-white text-on-surface">
        <ErrorState
          title="SnapFlick no pudo cargar"
          message="Ocurrió un error inesperado. Intenta recargar la página."
          onRetry={retry}
          details={error.digest ? `Código: ${error.digest}` : undefined}
        />
      </body>
    </html>
  );
}
