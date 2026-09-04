"use client";

import { useEffect, useState } from "react";
import type { Job } from "@/lib/types";
import { Icon } from "./Icon";

const STEPS = [
  { icon: "cloud_upload", label: "Subiendo imagen" },
  { icon: "content_cut", label: "Quitando el fondo" },
  { icon: "auto_fix_high", label: "Componiendo sobre el fondo de marca" },
  { icon: "auto_awesome", label: "Generando descripción con IA" },
  { icon: "category", label: "Ajustando categorías del catálogo" },
] as const;

// El backend procesa todo en una sola llamada síncrona (no manda progreso
// real paso a paso), así que estos pasos son una simulación con timings
// razonables — avanzan solos pero nunca superan el penúltimo paso hasta que
// la llamada real responde, para no "mentir" completando antes de tiempo.
const STEP_INTERVAL_MS = 1500;

export function AddProductModal({
  previewUrl,
  uploadPromise,
  onAdded,
  onClose,
}: {
  /**
   * URL del blob de la imagen, creada por el padre en el mismo evento
   * síncrono en el que el usuario eligió el archivo (`URL.createObjectURL`),
   * no en un efecto de este componente. En desarrollo, StrictMode monta un
   * efecto, lo limpia y lo vuelve a montar de inmediato — si la URL se creaba
   * y revocaba en un efecto de acá, esa limpieza revocaba el blob mientras la
   * miniatura seguía usándolo, y la imagen se quedaba rota para siempre. El
   * padre la revoca cuando cierra el modal (`onAdded`/`onClose`), no en un
   * efecto tampoco, por la misma razón.
   */
  previewUrl: string;
  /**
   * La llamada a `POST /jobs/{id}/products` (`addProduct`) ya despachada por
   * el padre, en el mismo evento síncrono de selección de archivo — no acá.
   * `add_product_to_job` en el backend NO es idempotente (agrega un producto
   * cada vez que se llama), así que si este componente disparara el POST
   * dentro de un efecto, el doble mount+cleanup+mount de StrictMode en
   * desarrollo lo mandaría dos veces de verdad (el cleanup no puede cancelar
   * un POST que ya llegó al servidor) y el producto quedaba duplicado. Acá
   * solo nos suscribimos a la promesa ya en vuelo.
   */
  uploadPromise: Promise<Job>;
  onAdded: (job: Job) => void;
  onClose: () => void;
}) {
  const [stepIndex, setStepIndex] = useState(0);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const timer = setInterval(() => {
      setStepIndex((i) => (i < STEPS.length - 1 ? i + 1 : i));
    }, STEP_INTERVAL_MS);

    uploadPromise
      .then((job) => {
        if (cancelled) return;
        clearInterval(timer);
        setStepIndex(STEPS.length - 1);
        setDone(true);
        setTimeout(() => {
          if (!cancelled) onAdded(job);
        }, 700);
      })
      .catch((err) => {
        if (cancelled) return;
        clearInterval(timer);
        setError(err instanceof Error ? err.message : "No se pudo agregar el producto.");
      });

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const currentStep = STEPS[stepIndex];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-inverse-surface/40 p-4">
      <div className="glass flex h-135 w-full max-w-sm flex-col items-center rounded-[28px] border border-outline-variant/40 p-8 text-center shadow-glow">
        {/* Miniatura persistente: se queda visible todo el tiempo, no depende del paso actual */}
        <div className="relative mb-5 h-24 w-24 shrink-0 overflow-hidden rounded-2xl bg-surface-container-high shadow-lg ring-4 ring-surface">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={previewUrl} alt="" className="h-full w-full object-cover" />
          {!error && !done && (
            <div className="absolute inset-0 rounded-2xl border-2 border-transparent border-t-primary animate-spin-slow [animation-duration:1.5s]" />
          )}
        </div>

        <h2 className="text-headline-md font-semibold text-on-surface">
          {error ? "Algo salió mal" : done ? "¡Listo!" : "Agregando producto"}
        </h2>
        {/* min-h reserva el espacio de 2 líneas: el mensaje de error es más largo
            que los demás y no debería empujar el resto del layout hacia abajo */}
        <p className="mb-2 flex min-h-12 items-center text-body-sm text-on-surface-variant">
          {error
            ? "Puedes cerrar e intentar de nuevo."
            : done
              ? "El producto se agregó al catálogo."
              : "La IA está procesando la foto…"}
        </p>

        {/* Este contenedor tiene alto fijo (flex-1 dentro de la tarjeta de alto
            fijo) para que el estado de error y el carrusel ocupen siempre el
            mismo espacio — la tarjeta no debe cambiar de tamaño según el texto. */}
        <div className="flex w-full flex-1 flex-col items-center justify-center">
          {error ? (
            <div className="flex w-full items-center gap-2 rounded-lg bg-error-container p-4 text-left text-on-error-container">
              <Icon name="error" />
              {error}
            </div>
          ) : (
            <>
              {/* Escenario tipo carrusel: un ícono grande al centro que "entra" con un
                  pop elástico cada vez que cambia de paso (key={stepIndex} lo remonta) */}
              <div className="relative mb-6 flex h-32 w-32 shrink-0 items-center justify-center">
                <div
                  className={`absolute inset-0 rounded-full transition-colors duration-500 ${
                    done ? "bg-ai-success/15" : "bg-primary-container/40"
                  }`}
                />
                <div
                  key={done ? "done" : stepIndex}
                  className="animate-step-pop relative flex h-20 w-20 items-center justify-center rounded-full bg-primary text-on-primary shadow-lg"
                >
                  <Icon name={done ? "check_circle" : currentStep.icon} className="text-[40px]" filled={done} />
                </div>
              </div>

              <p
                key={done ? "done-label" : currentStep.label}
                className="animate-step-pop mb-6 flex min-h-12 items-center justify-center font-mono text-label-lg text-on-background"
              >
                {done ? "Producto agregado" : currentStep.label}
              </p>

              {/* Puntos de progreso, estilo carrusel */}
              <div className="flex items-center gap-2">
                {STEPS.map((step, i) => (
                  <span
                    key={step.label}
                    className={`h-2 rounded-full transition-all duration-500 ${
                      i === stepIndex && !done
                        ? "w-6 bg-primary"
                        : i < stepIndex || done
                          ? "w-2 bg-primary/50"
                          : "w-2 bg-outline-variant"
                    }`}
                  />
                ))}
              </div>
            </>
          )}
        </div>

        {error && (
          <button
            onClick={onClose}
            className="flex w-full shrink-0 items-center justify-center gap-2 rounded-full border border-outline-variant px-6 py-2.5 font-mono text-label-md text-on-surface transition-colors hover:bg-surface-container-high"
          >
            Cerrar
          </button>
        )}
      </div>
    </div>
  );
}
