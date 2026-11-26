"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Copy, Check, Sparkles } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { useApp } from "@/components/providers";
import { apiFetch } from "@/lib/api";
import type { AssistantResult, JobMatch } from "@/lib/types";
import { cn } from "@/lib/utils";

const ACTIONS = [
  { id: "explain_match", label: "Explain Why Job Matches CV" },
  { id: "missing_skills", label: "Identify Missing Skills" },
  { id: "cv_improvements", label: "Truthful CV Improvements" },
  { id: "cover_letter", label: "Tailored Cover Letter" },
  { id: "interview_prep", label: "Interview Preparation" },
  { id: "learning_roadmap", label: "Skills to Learn Roadmap" },
  { id: "plain_english", label: "Plain-English Requirements" },
  { id: "compare_jobs", label: "Compare Selected Jobs" }
];

function AssistantContent() {
  const searchParams = useSearchParams();
  const initialJobId = searchParams.get("job_id") || "";
  const initialAction = searchParams.get("action") || "explain_match";
  const { compareIds } = useApp();

  const [jobs, setJobs] = useState<JobMatch[]>([]);
  const [selectedJobId, setSelectedJobId] = useState(initialJobId);
  const [action, setAction] = useState(initialAction);
  const [tone, setTone] = useState<"professional" | "concise" | "enthusiastic">("professional");
  const [customQuestion, setCustomQuestion] = useState("");
  const [result, setResult] = useState<AssistantResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    apiFetch<JobMatch[]>("/jobs")
      .then((list) => {
        setJobs(list);
        if (!selectedJobId && list.length > 0) {
          setSelectedJobId(list[0].job_id);
        }
      })
      .catch(() => {});
  }, []);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<AssistantResult>("/assistant/generate", {
        method: "POST",
        body: JSON.stringify({
          action,
          job_id: selectedJobId || null,
          compare_job_ids:
            action === "compare_jobs"
              ? compareIds.length >= 2
                ? compareIds
                : jobs.slice(0, 3).map((j) => j.job_id)
              : [],
          tone,
          user_message: customQuestion || null
        })
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!result) return;
    navigator.clipboard.writeText(result.content_markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Sparkles className="h-6 w-6 text-primary" /> Grounded AI Career Assistant
        </h1>
        <p className="text-sm text-muted-foreground">
          Every cover letter, gap report, and interview plan is strictly anchored to your verified CV—never
          fabricating employers, degrees, or skills.
        </p>
      </div>

      <div className="rounded-2xl border border-border bg-card p-6 space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-2">
            <label className="text-xs font-medium">Target Job Opportunity</label>
            <select
              value={selectedJobId}
              onChange={(e) => setSelectedJobId(e.target.value)}
              className="mt-1.5 w-full px-3.5 py-2 rounded-lg border border-border bg-background text-sm"
            >
              <option value="">General CV Readiness (No specific job)</option>
              {jobs.map((m) => (
                <option key={m.job_id} value={m.job_id}>
                  [{Math.round(m.overall_score)}%] {m.job.title} — {m.job.company_name} ({m.job.country})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-medium">Writing Tone</label>
            <select
              value={tone}
              onChange={(e) => setTone(e.target.value as any)}
              className="mt-1.5 w-full px-3.5 py-2 rounded-lg border border-border bg-background text-sm"
            >
              <option value="professional">Professional</option>
              <option value="concise">Concise & Direct</option>
              <option value="enthusiastic">Enthusiastic</option>
            </select>
          </div>
        </div>

        <div>
          <label className="text-xs font-medium block mb-2">Select Assistant Capability</label>
          <div className="flex flex-wrap gap-2">
            {ACTIONS.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => setAction(a.id)}
                className={cn(
                  "px-3 py-1.5 rounded-lg border text-xs font-medium transition",
                  action === a.id
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-background hover:bg-accent"
                )}
              >
                {a.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="text-xs font-medium">Optional Focus Note or Question</label>
          <input
            value={customQuestion}
            onChange={(e) => setCustomQuestion(e.target.value)}
            placeholder="e.g. Highlight my distributed systems project and ask about visa relocation..."
            className="mt-1 w-full px-3.5 py-2 rounded-lg border border-border bg-background text-sm"
          />
        </div>

        <button
          onClick={handleGenerate}
          disabled={loading}
          className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-semibold hover:opacity-90 disabled:opacity-50"
        >
          <Sparkles className="h-4 w-4" />
          {loading ? "Generating Grounded Output..." : "Generate with AI Career Assistant"}
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-sm text-rose-500">
          {error}
        </div>
      )}

      {result && (
        <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
            <div>
              <h2 className="font-bold text-lg">{result.title}</h2>
              <span className="text-[11px] text-muted-foreground">Engine: {result.generation_mode}</span>
            </div>
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs font-medium hover:bg-accent"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? "Copied" : "Copy Markdown"}
            </button>
          </div>

          {result.highlights.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {result.highlights.map((h, i) => (
                <span
                  key={i}
                  className="text-xs px-2.5 py-1 rounded-md bg-primary/10 text-primary font-medium"
                >
                  {h}
                </span>
              ))}
            </div>
          )}

          <div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap text-sm leading-relaxed">
            {result.content_markdown}
          </div>

          <div className="pt-3 border-t border-border text-[11px] text-muted-foreground">
            {result.disclaimer}
          </div>
        </div>
      )}
    </div>
  );
}

export default function AssistantPage() {
  return (
    <AppShell>
      <Suspense fallback={<div className="p-8 text-sm text-muted-foreground">Loading AI Career Assistant...</div>}>
        <AssistantContent />
      </Suspense>
    </AppShell>
  );
}
