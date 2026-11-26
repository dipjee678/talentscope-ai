"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  CheckCircle2,
  Loader2,
  XCircle
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { API_BASE_URL, apiFetch, getFreshAccessToken } from "@/lib/api";
import type { SearchSession } from "@/lib/types";
import { humanize } from "@/lib/utils";

const STAGE_STEPS = [
  { key: "cv_verification", label: "1. CV Analysis Agent" },
  { key: "discovering_jobs", label: "2. Job Discovery Agent" },
  { key: "extraction_complete", label: "3. Job Extraction Agent" },
  { key: "verification_complete", label: "4. Verification & Dedup Agent" },
  { key: "matching_complete", label: "5. Matching Engine" },
  { key: "ranking_complete", label: "6. Ranking Agent" },
  { key: "completed", label: "7. Reporting Agent" }
];

export default function SearchProgressPage() {
  const params = useParams<{ id: string }>();
  const sessionId = params.id;
  const [session, setSession] = useState<SearchSession | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchSession = async () => {
    try {
      const s = await apiFetch<SearchSession>(`/searches/${sessionId}`);
      setSession(s);
    } catch (err: any) {
      setError(err.message);
    }
  };

  useEffect(() => {
    if (!sessionId) return;
    fetchSession();

    let es: EventSource | null = null;
    let cancelled = false;
    // SSE drives fast updates; polling is the fallback if the stream drops (proxies, restarts).
    getFreshAccessToken().then((token) => {
      if (cancelled) return;
      es = new EventSource(
        `${API_BASE_URL}/searches/${sessionId}/stream${token ? `?token=${encodeURIComponent(token)}` : ""}`
      );
      es.onmessage = (evt) => {
        fetchSession();
        try {
          if (JSON.parse(evt.data)?.terminal) es?.close();
        } catch {
          // ignore malformed event
        }
      };
      es.onerror = () => {
        es?.close();
      };
    });

    const poll = setInterval(() => {
      fetchSession();
    }, 3000);

    return () => {
      cancelled = true;
      es?.close();
      clearInterval(poll);
    };
  }, [sessionId]);

  const isRunning = session?.status === "queued" || session?.status === "running";

  return (
    <AppShell>
      <div className="max-w-5xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-primary">
              <Bot className="h-4 w-4" /> Autonomous Multi-Agent Execution
            </div>
            <h1 className="text-2xl font-bold tracking-tight mt-1">
              {session?.status === "completed"
                ? "Your matches are ready"
                : session?.status === "failed"
                ? "Search Encountered an Issue"
                : session?.status === "cancelled"
                ? "Search Cancelled"
                : "Finding jobs that fit your CV…"}
            </h1>
            {isRunning && (
              <p className="mt-1 text-sm text-muted-foreground">
                This usually takes 1–3 minutes. You can leave this page — results will appear on your dashboard.
              </p>
            )}
            {session?.status === "failed" && session.error_message && (
              <p className="mt-1 text-sm text-rose-500">{session.error_message}</p>
            )}
          </div>

          {session?.status === "completed" && (
            <Link
              href={`/jobs?session_id=${session.id}`}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-semibold shadow-sm hover:opacity-90"
            >
              View {session.jobs_matched_count} Matching Jobs <ArrowRight className="h-4 w-4" />
            </Link>
          )}
        </div>

        {error && (
          <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-sm text-rose-500">
            {error}
          </div>
        )}

        {session && (
          <>
            {/* Progress Bar */}
            <div className="rounded-xl border border-border bg-card p-6 space-y-4">
              <div className="flex items-center justify-between text-sm font-medium">
                <span className="flex items-center gap-2">
                  {isRunning ? (
                    <Loader2 className="h-4 w-4 text-primary animate-spin" />
                  ) : session.status === "completed" ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                  ) : (
                    <XCircle className="h-4 w-4 text-rose-500" />
                  )}
                  {humanize(session.current_stage)}
                </span>
                <span className="font-bold text-primary">{session.progress_percent}%</span>
              </div>
              <div className="h-2.5 w-full rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-500"
                  style={{ width: `${session.progress_percent}%` }}
                />
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 pt-2">
                {[
                  { label: "Sources Searched", val: session.sources_searched_count },
                  { label: "Raw Discovered", val: session.jobs_discovered_count },
                  { label: "Verified / Active", val: session.jobs_verified_count },
                  { label: "Duplicates Removed", val: session.duplicates_removed_count },
                  { label: "Below Threshold", val: session.below_threshold_count },
                  { label: "Qualifying Matches", val: session.jobs_matched_count }
                ].map((m) => (
                  <div key={m.label} className="p-3 rounded-lg bg-muted/50 border border-border/60">
                    <div className="text-[11px] text-muted-foreground">{m.label}</div>
                    <div className="text-lg font-bold mt-0.5">{m.val}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Agent Pipeline Badges */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-2.5">
              {STAGE_STEPS.map((st, idx) => {
                const thresholdPct = (idx + 1) * 14;
                const done =
                  session.status === "completed" || session.progress_percent >= thresholdPct;
                return (
                  <div
                    key={st.key}
                    className={`p-3 rounded-xl border text-xs font-medium ${
                      done
                        ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                        : "border-border bg-card text-muted-foreground"
                    }`}
                  >
                    {st.label}
                  </div>
                );
              })}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Live Agent Execution Logs */}
              <div className="rounded-xl border border-border bg-card p-5 space-y-3">
                <h2 className="font-semibold text-sm">Live Agent Execution Logs</h2>
                <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                  {session.logs.length === 0 ? (
                    <p className="text-xs text-muted-foreground">Waiting for first agent log...</p>
                  ) : (
                    session.logs.map((lg) => (
                      <div
                        key={lg.id}
                        className="p-2.5 rounded-lg bg-muted/40 border border-border/50 text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono font-semibold text-primary">{lg.agent_name}</span>
                          {lg.duration_ms != null && (
                            <span className="text-[10px] text-muted-foreground">{lg.duration_ms} ms</span>
                          )}
                        </div>
                        <div className="text-foreground/90">{lg.message}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Transparent Source Coverage & Limitations */}
              <div className="rounded-xl border border-border bg-card p-5 space-y-4">
                <h2 className="font-semibold text-sm">Search Coverage & Source Limitations</h2>
                {session.generated_queries.length > 0 && (
                  <div className="text-xs">
                    <span className="text-muted-foreground">Synthesized Queries: </span>
                    {session.generated_queries.map((q) => (
                      <span
                        key={q}
                        className="inline-block mr-1.5 mb-1 px-2 py-0.5 rounded bg-primary/10 text-primary font-medium"
                      >
                        {q}
                      </span>
                    ))}
                  </div>
                )}

                {session.sources_searched.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
                      Permitted Sources Searched ({session.sources_searched.length})
                    </div>
                    <div className="space-y-1 max-h-40 overflow-y-auto text-xs">
                      {session.sources_searched.map((src) => (
                        <div
                          key={src.slug}
                          className="flex items-center justify-between py-1 border-b border-border/50"
                        >
                          <span>{src.name}</span>
                          <span className="font-mono text-muted-foreground">
                            {src.jobs_found} jobs ({src.pages_fetched}p)
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {session.sources_unavailable.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="text-xs font-medium text-amber-600 dark:text-amber-400 flex items-center gap-1">
                      <AlertTriangle className="h-3.5 w-3.5" /> Unconfigured / Restricted Sources Disclosed
                    </div>
                    <div className="space-y-1.5 max-h-40 overflow-y-auto text-[11px] text-muted-foreground">
                      {session.sources_unavailable.map((u, i) => (
                        <div key={i} className="p-2 rounded bg-muted/50">
                          <strong className="text-foreground">{u.name}:</strong> {u.reason}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
