"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ExternalLink,
  Sparkles
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { ScoreRing } from "@/components/score-ring";
import { apiFetch } from "@/lib/api";
import type { JobMatch } from "@/lib/types";
import { formatDate } from "@/lib/utils";

export default function JobDetailsPage() {
  const params = useParams<{ id: string }>();
  const jobId = params.id;
  const [match, setMatch] = useState<JobMatch | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;
    apiFetch<JobMatch>(`/jobs/${jobId}`)
      .then((m) => setMatch(m))
      .catch((err) => setError(err.message));
  }, [jobId]);

  return (
    <AppShell>
      <div className="max-w-5xl space-y-6">
        <Link
          href="/jobs"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to Job Results
        </Link>

        {error && (
          <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-sm text-rose-500">
            {error}
          </div>
        )}

        {match && (
          <>
            <div className="rounded-2xl border border-border bg-card p-6 flex flex-wrap items-start justify-between gap-6">
              <div className="space-y-2 max-w-2xl">
                <div className="text-xs font-medium text-muted-foreground">
                  {match.job.company_name} • Source: {match.job.source_name} •{" "}
                  <span className="uppercase">{match.job.verification_status.replace("_", " ")}</span>
                </div>
                <h1 className="text-2xl font-bold tracking-tight">{match.job.title}</h1>
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span className="px-2.5 py-0.5 rounded bg-muted text-foreground font-medium">
                    {match.job.location_raw}
                  </span>
                  <span className="px-2.5 py-0.5 rounded bg-muted text-foreground font-medium capitalize">
                    {match.job.work_mode}
                  </span>
                  <span className="px-2.5 py-0.5 rounded bg-muted text-foreground font-medium">
                    {match.job.employment_type}
                  </span>
                  {match.job.salary_raw && (
                    <span className="px-2.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-semibold">
                      {match.job.salary_raw}
                    </span>
                  )}
                </div>
                <div className="text-xs text-muted-foreground pt-1">
                  Published: {formatDate(match.job.published_at)} • Deadline:{" "}
                  {formatDate(match.job.application_deadline)}
                </div>
              </div>

              <div className="flex items-center gap-4">
                <ScoreRing score={match.overall_score} size={74} />
                <div className="flex flex-col gap-2">
                  <a
                    href={match.job.apply_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-1.5 px-5 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-semibold hover:opacity-90"
                  >
                    Apply Direct <ExternalLink className="h-4 w-4" />
                  </a>
                  <Link
                    href={`/assistant?job_id=${match.job.id}`}
                    className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl border border-border text-xs font-medium hover:bg-accent"
                  >
                    <Sparkles className="h-3.5 w-3.5 text-primary" /> Generate Cover Letter & Prep
                  </Link>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-border bg-card p-6 space-y-5">
              <div>
                <h2 className="font-semibold text-base">Explainable 6-Dimension Matching Breakdown</h2>
                <p className="text-xs text-muted-foreground mt-1">{match.score_explanation}</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {[
                  { label: "Technical Skills", score: match.technical_skills_score, wKey: "technical_skills" },
                  { label: "Work Experience", score: match.experience_score, wKey: "work_experience" },
                  { label: "Education", score: match.education_score, wKey: "education" },
                  {
                    label: "Required Qualifications",
                    score: match.qualifications_score,
                    wKey: "required_qualifications"
                  },
                  {
                    label: "Projects & Achievements",
                    score: match.projects_score,
                    wKey: "projects_achievements"
                  },
                  { label: "Job Role Relevance", score: match.role_relevance_score, wKey: "role_relevance" }
                ].map((dim) => (
                  <div key={dim.label} className="p-3.5 rounded-xl border border-border bg-background space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium">{dim.label}</span>
                      <span className="font-bold">
                        {dim.score}%{" "}
                        <span className="text-muted-foreground font-normal">
                          (wt {match.weights_used?.[dim.wKey] ?? 0}%)
                        </span>
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-muted overflow-hidden">
                      <div className="h-full bg-primary" style={{ width: `${Math.min(100, dim.score)}%` }} />
                    </div>
                  </div>
                ))}
              </div>

              {match.explicit_disqualifiers.length > 0 && (
                <div className="p-4 rounded-xl border border-rose-500/40 bg-rose-500/10 text-xs text-rose-600 dark:text-rose-300 space-y-1">
                  <div className="font-semibold flex items-center gap-1.5">
                    <AlertTriangle className="h-4 w-4" /> Explicit Disqualifying / Restrictive Criteria Detected:
                  </div>
                  {match.explicit_disqualifiers.map((d, idx) => (
                    <div key={idx}>• {d}</div>
                  ))}
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20 space-y-2">
                  <div className="font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                    <CheckCircle2 className="h-4 w-4" /> Matched Skills & Strengths
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {match.matched_skills.map((s) => (
                      <span key={s} className="px-2 py-0.5 rounded bg-emerald-500/15 font-medium">
                        {s}
                      </span>
                    ))}
                  </div>
                  <ul className="space-y-1 text-muted-foreground pt-1">
                    {match.strengths.map((s, i) => (
                      <li key={i}>• {s}</li>
                    ))}
                  </ul>
                </div>

                <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/20 space-y-2">
                  <div className="font-semibold text-amber-600 dark:text-amber-400">
                    Missing Mandatory / Preferred Skills & Weaknesses
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {match.missing_mandatory_skills.map((s) => (
                      <span key={s} className="px-2 py-0.5 rounded bg-rose-500/15 text-rose-500 font-medium">
                        Mandatory: {s}
                      </span>
                    ))}
                    {match.missing_preferred_skills.map((s) => (
                      <span key={s} className="px-2 py-0.5 rounded bg-amber-500/15 font-medium">
                        Preferred: {s}
                      </span>
                    ))}
                  </div>
                  <ul className="space-y-1 text-muted-foreground pt-1">
                    {match.weaknesses.map((w, i) => (
                      <li key={i}>• {w}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-border bg-card p-6 space-y-3">
              <h2 className="font-semibold text-base">Verified Job Description</h2>
              <div className="text-sm text-foreground/90 whitespace-pre-line leading-relaxed">
                {match.job.description_text || "No extended description provided by source."}
              </div>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
