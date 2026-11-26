"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Bell,
  Bookmark,
  Briefcase,
  CheckCircle2,
  Compass,
  FileText,
  FileUp,
  Sparkles
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { ScoreRing } from "@/components/score-ring";
import { apiFetch } from "@/lib/api";
import { useApp } from "@/components/providers";
import { formatDate } from "@/lib/utils";

export default function DashboardPage() {
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { user } = useApp();

  useEffect(() => {
    apiFetch("/dashboard/summary")
      .then((data) => setSummary(data))
      .catch((err) => setError(err.message || "Could not load your dashboard."))
      .finally(() => setLoading(false));
  }, []);

  const firstName = (user?.full_name || "").split(" ")[0];
  const hasCv = (summary?.cv_count ?? 0) > 0;
  const hasSearch = (summary?.total_searches ?? 0) > 0;
  const hasMatches = (summary?.total_qualifying_matches ?? 0) > 0;
  const steps = [
    { done: hasCv, title: "Upload your CV", text: "PDF or Word — we read your skills and experience.", href: "/cv/upload", cta: "Upload CV" },
    { done: hasCv, title: "Check your profile", text: "Fix anything we read wrong so scores are accurate.", href: "/profile", cta: "Review profile" },
    { done: hasSearch, title: "Run your first search", text: "Pick countries and a minimum match %.", href: "/search/new", cta: "Start search" },
    { done: hasMatches, title: "Review your matches", text: "Every score comes with a plain explanation.", href: "/jobs", cta: "See matches" }
  ];
  const showOnboarding = !loading && !error && !(hasCv && hasSearch);

  return (
    <AppShell>
      <div className="space-y-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              {firstName ? `Welcome back, ${firstName}` : "Dashboard"}
            </h1>
            <p className="text-sm text-muted-foreground">
              {summary?.active_cv_filename
                ? `Active CV: ${summary.active_cv_filename} ${
                    summary.profile_headline ? `• ${summary.profile_headline}` : ""
                  }`
                : "Upload your CV to start finding jobs that fit you."}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/cv/upload"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-border bg-card text-sm font-medium hover:bg-accent transition"
            >
              <FileUp className="h-4 w-4" /> Upload CV
            </Link>
            <Link
              href="/search/new"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:opacity-90 transition"
            >
              <Compass className="h-4 w-4" /> Start AI Job Search
            </Link>
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-500">
            {error}{" "}
            <button onClick={() => window.location.reload()} className="underline font-medium">
              Try again
            </button>
          </div>
        )}

        {showOnboarding && (
          <section className="rounded-2xl border border-primary/30 bg-gradient-to-br from-primary/10 via-card to-card p-6">
            <h2 className="text-lg font-semibold">Get started in 4 steps</h2>
            <p className="text-sm text-muted-foreground">Takes about 3 minutes. You can come back to any step later.</p>
            <ol className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {steps.map((step, idx) => {
                const isNext = !step.done && steps.slice(0, idx).every((s) => s.done);
                return (
                  <li
                    key={step.title}
                    className={`rounded-xl border p-4 bg-card ${isNext ? "border-primary shadow-sm" : "border-border"}`}
                  >
                    <div className="flex items-center gap-2 text-sm font-semibold">
                      {step.done ? (
                        <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                      ) : (
                        <span className="flex h-5 w-5 items-center justify-center rounded-full border border-border text-[11px]">
                          {idx + 1}
                        </span>
                      )}
                      <span className={step.done ? "text-muted-foreground line-through" : ""}>{step.title}</span>
                    </div>
                    <p className="mt-1.5 text-xs text-muted-foreground">{step.text}</p>
                    {!step.done && (
                      <Link
                        href={step.href}
                        className={`mt-3 inline-flex items-center gap-1 text-xs font-semibold ${
                          isNext ? "text-primary" : "text-muted-foreground hover:text-foreground"
                        }`}
                      >
                        {step.cta} <ArrowRight className="h-3 w-3" />
                      </Link>
                    )}
                  </li>
                );
              })}
            </ol>
          </section>
        )}

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((n) => (
              <div key={n} className="h-28 rounded-xl border border-border bg-card animate-pulse" />
            ))}
          </div>
        ) : (
          <>
            {/* KPI Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="rounded-xl border border-border bg-card p-5">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>CV Versions</span>
                  <FileText className="h-4 w-4 text-primary" />
                </div>
                <div className="mt-2 text-2xl font-bold">{summary?.cv_count ?? 0}</div>
                <Link href="/profile" className="mt-2 inline-block text-xs text-primary hover:underline">
                  View extracted profile →
                </Link>
              </div>

              <div className="rounded-xl border border-border bg-card p-5">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Matching Jobs</span>
                  <Briefcase className="h-4 w-4 text-emerald-500" />
                </div>
                <div className="mt-2 text-2xl font-bold">{summary?.total_qualifying_matches ?? 0}</div>
                <Link href="/jobs" className="mt-2 inline-block text-xs text-primary hover:underline">
                  Browse verified matches →
                </Link>
              </div>

              <div className="rounded-xl border border-border bg-card p-5">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Saved Jobs</span>
                  <Bookmark className="h-4 w-4 text-amber-500" />
                </div>
                <div className="mt-2 text-2xl font-bold">{summary?.saved_jobs_count ?? 0}</div>
                <Link href="/tracker" className="mt-2 inline-block text-xs text-primary hover:underline">
                  Open application tracker →
                </Link>
              </div>

              <div className="rounded-xl border border-border bg-card p-5">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Applications</span>
                  <Sparkles className="h-4 w-4 text-blue-500" />
                </div>
                <div className="mt-2 text-2xl font-bold">
                  {Object.values((summary?.application_pipeline || {}) as Record<string, number>).reduce(
                    (a, b) => a + b,
                    0
                  )}
                </div>
                <Link href="/assistant" className="mt-2 inline-block text-xs text-primary hover:underline">
                  Tailor cover letter & prep →
                </Link>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Top Matches */}
              <div className="lg:col-span-2 rounded-xl border border-border bg-card p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold text-base">Your Best Matches</h2>
                  <Link href="/jobs" className="text-xs text-primary font-medium hover:underline">
                    View all →
                  </Link>
                </div>

                {!summary?.top_matches?.length ? (
                  <div className="py-10 text-center text-sm text-muted-foreground space-y-3">
                    <p>No matched jobs yet. Upload your CV and run your first autonomous AI job search.</p>
                    <Link
                      href={summary?.cv_count ? "/search/new" : "/cv/upload"}
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-semibold"
                    >
                      {summary?.cv_count ? "Configure AI Job Search" : "Upload Your CV"}{" "}
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                ) : (
                  <div className="divide-y divide-border">
                    {summary.top_matches.map((m: any) => (
                      <div key={m.id} className="py-3.5 flex items-center justify-between gap-4">
                        <div className="min-w-0">
                          <Link
                            href={`/jobs/${m.job.id}`}
                            className="font-semibold text-sm hover:text-primary transition block truncate"
                          >
                            {m.job.title}
                          </Link>
                          <div className="text-xs text-muted-foreground">
                            {m.job.company_name} • {m.job.location_raw} •{" "}
                            <span className="capitalize">{m.job.work_mode}</span>
                          </div>
                        </div>
                        <ScoreRing score={m.overall_score} size={46} showLabel={false} />
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Recent Searches & Notifications */}
              <div className="space-y-6">
                <div className="rounded-xl border border-border bg-card p-5 space-y-3">
                  <h2 className="font-semibold text-base">Recent Searches</h2>
                  {!summary?.recent_searches?.length ? (
                    <p className="text-xs text-muted-foreground py-4">No search sessions run yet.</p>
                  ) : (
                    <div className="space-y-2.5">
                      {summary.recent_searches.map((s: any) => (
                        <Link
                          key={s.id}
                          href={`/search/${s.id}`}
                          className="block p-3 rounded-lg border border-border hover:bg-accent transition text-xs space-y-1"
                        >
                          <div className="flex items-center justify-between font-medium">
                            <span className="truncate">
                              {(s.config_snapshot?.target_countries || []).join(", ") || "Global Search"}
                            </span>
                            <span className="uppercase text-[10px] px-1.5 py-0.5 rounded bg-primary/15 text-primary">
                              {s.status}
                            </span>
                          </div>
                          <div className="text-muted-foreground">
                            {s.jobs_matched_count} matches ≥ {s.config_snapshot?.min_match_score ?? 50}% •{" "}
                            {formatDate(s.created_at)}
                          </div>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>

                <div className="rounded-xl border border-border bg-card p-5 space-y-3">
                  <div className="flex items-center gap-2 font-semibold text-sm">
                    <Bell className="h-4 w-4 text-primary" /> Recent Notifications
                  </div>
                  {!summary?.notifications?.length ? (
                    <p className="text-xs text-muted-foreground">No notifications yet.</p>
                  ) : (
                    <div className="space-y-2">
                      {summary.notifications.slice(0, 4).map((n: any) => (
                        <div key={n.id} className="p-2.5 rounded-lg bg-muted/50 text-xs space-y-0.5">
                          <div className="font-medium">{n.title}</div>
                          <div className="text-muted-foreground">{n.body}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
