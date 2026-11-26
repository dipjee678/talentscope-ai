"use client";

import React from "react";
import { cn } from "@/lib/utils";

export function scoreTier(score: number): { tone: string; label: string } {
  if (score >= 75) return { tone: "text-emerald-500", label: "Strong fit" };
  if (score >= 60) return { tone: "text-blue-500", label: "Good fit" };
  if (score >= 45) return { tone: "text-amber-500", label: "Partial fit" };
  return { tone: "text-rose-500", label: "Low fit" };
}

export function ScoreRing({
  score,
  size = 56,
  showLabel = true
}: {
  score: number;
  size?: number;
  showLabel?: boolean;
}) {
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const strokeWidth = 5;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clamped / 100) * circumference;

  const { tone, label } = scoreTier(clamped);

  return (
    <div
      className="inline-flex flex-col items-center gap-0.5"
      title={`${label} (${clamped}%). Measures how well your CV fits this job's requirements — not an interview guarantee.`}
      aria-label={`${label}, ${clamped} percent`}
    >
      <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            strokeWidth={strokeWidth}
            className="stroke-muted fill-none"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className={cn("fill-none transition-all duration-500", tone, "stroke-current")}
          />
        </svg>
        <span className="absolute text-xs font-bold tracking-tight">{clamped}%</span>
      </div>
      {showLabel && (
        <span className={cn("text-[10px] font-semibold uppercase tracking-wider", tone)}>{label}</span>
      )}
    </div>
  );
}
