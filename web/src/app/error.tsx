"use client";

import { useEffect } from "react";
import { AppShell } from "@/components/AppShell";
import { ErrorState } from "@/components/ErrorState";

export default function ErrorBoundary({
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
    <AppShell>
      <ErrorState
        title="Ocurrió un error inesperado"
        message="Algo falló al mostrar esta página. Puedes intentar de nuevo o volver al inicio."
        onRetry={retry}
        actionHref="/"
        actionLabel="Ir al inicio"
        details={error.digest ? `Código: ${error.digest}` : undefined}
      />
    </AppShell>
  );
}
