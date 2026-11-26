"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ExternalLink, Sparkles, Trash2 } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { useApp } from "@/components/providers";
import { ScoreRing } from "@/components/score-ring";
import { apiFetch } from "@/lib/api";
import type { JobMatch } from "@/lib/types";

export default function JobComparisonPage() {
  const { compareIds, toggleCompareId, clearCompareIds } = useApp();
  const [comparison, setComparison] = useState<{
    items: JobMatch[];
    shared_matched_skills: string[];
    shared_missing_skills: string[];
    recommendation_summary: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (compareIds.length < 2) {
      setComparison(null);
      return;
    }
    setError(null);
    apiFetch("/jobs/compare", {
      method: "POST",
      body: JSON.stringify({ job_ids: compareIds })
    })
      .then((res) => setComparison(res))
      .catch((err) => setError(err.message));
  }, [compareIds]);

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Side-by-Side Job Comparison</h1>
            <p className="text-sm text-muted-foreground">
              Compare 2 to 4 opportunities across CV alignment dimensions, missing skills, work mode, and salary.
            </p>
          </div>
          {compareIds.length > 0 && (
            <button
              onClick={clearCompareIds}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-border text-xs font-medium hover:bg-accent"
            >
              <Trash2 className="h-3.5 w-3.5" /> Clear Selection ({compareIds.length})
            </button>
          )}
        </div>

        {compareIds.length < 2 ? (
          <div className="rounded-xl border border-border bg-card p-10 text-center space-y-3">
            <p className="text-sm text-muted-foreground">
              Select at least 2 jobs (currently {compareIds.length} selected) on the Job Results page using the{" "}
              <strong>Compare</strong> button.
            </p>
            <Link
              href="/jobs"
              className="inline-block px-4 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-semibold"
            >
              Browse Matching Jobs →
            </Link>
          </div>
        ) : error ? (
          <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-sm text-rose-500">
            {error}
          </div>
        ) : comparison ? (
          <>
            <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 flex flex-wrap items-center justify-between gap-4 text-xs">
              <div>
                <span className="font-semibold text-primary block mb-0.5">AI Comparative Summary</span>
                <span>{comparison.recommendation_summary}</span>
              </div>
              <Link
                href="/assistant?action=compare_jobs"
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-primary text-primary-foreground font-semibold"
              >
                <Sparkles className="h-3.5 w-3.5" /> Deep Compare in AI Assistant
              </Link>
            </div>

            <div className="overflow-x-auto rounded-xl border border-border bg-card">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-border bg-muted/40">
                    <th className="p-4 w-44 font-semibold">Criterion</th>
                    {comparison.items.map((it) => (
                      <th key={it.job_id} className="p-4 min-w-[230px] align-top">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div className="text-muted-foreground font-normal">{it.job.company_name}</div>
                            <Link href={`/jobs/${it.job_id}`} className="font-bold text-sm hover:text-primary">
                              {it.job.title}
                            </Link>
                          </div>
                          <button
                            onClick={() => toggleCompareId(it.job_id)}
                            className="text-muted-foreground hover:text-rose-500"
                            title="Remove"
                          >
                            ✕
                          </button>
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  <tr>
                    <td className="p-4 font-medium">Overall CV Match</td>
                    {comparison.items.map((it) => (
                      <td key={it.job_id} className="p-4">
                        <ScoreRing score={it.overall_score} size={50} showLabel={false} />
                      </td>
                    ))}
                  </tr>
                  {[
                    { label: "Technical Skills Score", key: "technical_skills_score" },
                    { label: "Work Experience Score", key: "experience_score" },
                    { label: "Education Score", key: "education_score" },
                    { label: "Qualifications Score", key: "qualifications_score" },
                    { label: "Projects Score", key: "projects_score" },
                    { label: "Role Relevance Score", key: "role_relevance_score" }
                  ].map((row) => (
                    <tr key={row.key}>
                      <td className="p-4 font-medium text-muted-foreground">{row.label}</td>
                      {comparison.items.map((it: any) => (
                        <td key={it.job_id} className="p-4 font-semibold">
                          {it[row.key]}%
                        </td>
                      ))}
                    </tr>
                  ))}
                  <tr>
                    <td className="p-4 font-medium text-muted-foreground">Location & Work Mode</td>
                    {comparison.items.map((it) => (
                      <td key={it.job_id} className="p-4">
                        {it.job.location_raw} ({it.job.work_mode})
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-4 font-medium text-muted-foreground">Salary</td>
                    {comparison.items.map((it) => (
                      <td key={it.job_id} className="p-4 font-medium text-emerald-600 dark:text-emerald-400">
                        {it.job.salary_raw || "Not disclosed"}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-4 font-medium text-muted-foreground">Matched Skills</td>
                    {comparison.items.map((it) => (
                      <td key={it.job_id} className="p-4">
                        {it.matched_skills.join(", ") || "—"}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-4 font-medium text-muted-foreground">Mandatory Skill Gaps</td>
                    {comparison.items.map((it) => (
                      <td key={it.job_id} className="p-4 text-rose-500">
                        {it.missing_mandatory_skills.join(", ") || "None"}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-4 font-medium text-muted-foreground">Direct Apply</td>
                    {comparison.items.map((it) => (
                      <td key={it.job_id} className="p-4">
                        <a
                          href={it.job.apply_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground font-semibold"
                        >
                          Apply <ExternalLink className="h-3 w-3" />
                        </a>
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </div>
    </AppShell>
  );
}
