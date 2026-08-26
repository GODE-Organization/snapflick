"use client";

import { useState } from "react";

export function BeforeAfterSlider({
  beforeUrl,
  afterUrl,
  alt,
}: {
  beforeUrl: string;
  afterUrl: string;
  alt: string;
}) {
  const [pct, setPct] = useState(50);

  return (
    <div className="flex flex-col gap-2">
      <div className="relative aspect-square w-full select-none overflow-hidden rounded-lg bg-surface-container-low">
        {/* eslint-disable @next/next/no-img-element */}
        <img src={afterUrl} alt={`${alt} (procesado)`} className="absolute inset-0 h-full w-full object-cover" />
        <div className="absolute inset-0 overflow-hidden" style={{ width: `${pct}%` }}>
          <img
            src={beforeUrl}
            alt={`${alt} (original)`}
            className="h-full w-full max-w-none object-cover"
            style={{ width: `${100 / (pct / 100)}%` }}
          />
        </div>
        {/* eslint-enable @next/next/no-img-element */}
        <div className="absolute inset-y-0 w-0.5 bg-white shadow-glow" style={{ left: `${pct}%` }} />
      </div>
      <input
        type="range"
        min={0}
        max={100}
        value={pct}
        onChange={(e) => setPct(Number(e.target.value))}
        className="w-full accent-primary"
        aria-label="Comparar antes y después"
      />
      <div className="flex justify-between font-mono text-label-sm text-on-surface-variant">
        <span>Original</span>
        <span>Procesado</span>
      </div>
    </div>
  );
}
