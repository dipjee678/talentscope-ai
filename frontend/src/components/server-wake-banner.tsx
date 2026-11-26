"use client";

import React, { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { SLOW_EVENT } from "@/lib/api";

/** Friendly notice while requests are slow — typically a free-tier server waking from sleep. */
export function ServerWakeBanner() {
  const [pending, setPending] = useState(0);

  useEffect(() => {
    const onSlow = (e: Event) => setPending((e as CustomEvent<number>).detail);
    window.addEventListener(SLOW_EVENT, onSlow);
    return () => window.removeEventListener(SLOW_EVENT, onSlow);
  }, []);

  if (pending === 0) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2 flex items-center gap-3 rounded-full border border-border bg-card/95 px-4 py-2.5 text-sm shadow-lg backdrop-blur"
    >
      <Loader2 className="h-4 w-4 animate-spin text-primary" />
      <span>
        Waking up the server — this can take up to a minute after a quiet period.
      </span>
    </div>
  );
}
