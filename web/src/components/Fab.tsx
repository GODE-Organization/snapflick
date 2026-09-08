"use client";

import Link from "next/link";
import { useState } from "react";
import { Icon } from "./Icon";

export interface FabAction {
  label: string;
  icon: string;
  href?: string;
  onClick?: () => void;
}

/** Botón de acción flotante, fijo en la esquina inferior derecha. Con una sola
 * acción se dispara directo al hacer clic; con varias, despliega un mini menú
 * hacia arriba con una opción por fila. */
export function Fab({ actions }: { actions: FabAction[] }) {
  const [open, setOpen] = useState(false);

  if (actions.length === 0) return null;

  const single = actions.length === 1 ? actions[0] : null;

  function runAction(action: FabAction) {
    setOpen(false);
    action.onClick?.();
  }

  return (
    <div className="fixed bottom-6 right-6 z-40 flex flex-col items-end gap-3">
      {!single && open && (
        <div className="flex flex-col items-end gap-2">
          {actions.map((action) =>
            action.href ? (
              <Link
                key={action.label}
                href={action.href}
                onClick={() => setOpen(false)}
                className="flex items-center gap-2 rounded-full bg-surface px-4 py-2.5 font-mono text-label-md text-on-surface shadow-lg transition-transform hover:-translate-y-0.5"
              >
                {action.label}
                <Icon name={action.icon} className="text-[18px] text-primary" />
              </Link>
            ) : (
              <button
                key={action.label}
                type="button"
                onClick={() => runAction(action)}
                className="flex items-center gap-2 rounded-full bg-surface px-4 py-2.5 font-mono text-label-md text-on-surface shadow-lg transition-transform hover:-translate-y-0.5"
              >
                {action.label}
                <Icon name={action.icon} className="text-[18px] text-primary" />
              </button>
            ),
          )}
        </div>
      )}

      {single ? (
        single.href ? (
          <Link
            href={single.href}
            title={single.label}
            className="flex h-14 w-14 items-center justify-center rounded-full gradient-ai text-white shadow-glow transition-transform hover:scale-105"
          >
            <Icon name={single.icon} className="text-[26px]" />
          </Link>
        ) : (
          <button
            type="button"
            onClick={() => runAction(single)}
            title={single.label}
            className="flex h-14 w-14 items-center justify-center rounded-full gradient-ai text-white shadow-glow transition-transform hover:scale-105"
          >
            <Icon name={single.icon} className="text-[26px]" />
          </button>
        )
      ) : (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          title={open ? "Cerrar" : "Acciones"}
          className="flex h-14 w-14 items-center justify-center rounded-full gradient-ai text-white shadow-glow transition-transform hover:scale-105"
        >
          <Icon name={open ? "close" : "add"} className="text-[26px]" />
        </button>
      )}
    </div>
  );
}
