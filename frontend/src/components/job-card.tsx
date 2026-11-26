"use client";

import React from "react";
import Link from "next/link";
import {
  Bookmark,
  BookmarkCheck,
  Building2,
  Calendar,
  CheckCircle2,
  Clock,
  ExternalLink,
  EyeOff,
  GitCompare,
  Globe2,
  ShieldAlert,
  ShieldCheck,
  Sparkles
} from "lucide-react";
import type { JobMatch } from "@/lib/types";
import { ScoreRing } from "@/components/score-ring";
import { cn, formatDate } from "@/lib/utils";

interface JobCardProps {
  match: JobMatch;
  isCompared: boolean;
  onToggleCompare: (jobId: string) => void;
  onToggleSave: (jobId: string, currentlySaved: boolean) => void;
  onMarkApplied: (jobId: string) => void;
  onHide: (jobId: string) => void;
}

export function JobCard({
  match,
  isCompared,
  onToggleCompare,
  onToggleSave,
  onMarkApplied,
  onHide
}: JobCardProps) {
  const { job } = match;

  const verBadge =
    job.verification_status === "verified_active" ? (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
        <ShieldCheck className="h-3 w-3" /> Verified Active
      </span>
    ) : (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400">
        <ShieldAlert className="h-3 w-3" /> Unverified Host
      </span>
    );

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm hover:border-primary/40 transition-all flex flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3.5 min-w-0">
          {job.company_logo_url ? (
            <img
              src={job.company_logo_url}
              alt={job.company_name}
              className="h-11 w-11 rounded-lg object-contain border border-border bg-white p-1 shrink-0"
            />
          ) : (
            <div className="h-11 w-11 rounded-lg border border-border bg-muted flex items-center justify-center shrink-0">
              <Building2 className="h-5 w-5 text-muted-foreground" />
            </div>
          )}
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground">{job.company_name}</span>
              {verBadge}
              {job.is_direct_company_link && (
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
                  Direct Employer Link
                </span>
              )}
            </div>
            <Link
              href={`/jobs/${job.id}`}
              className="mt-1 block text-base sm:text-lg font-semibold text-foreground hover:text-primary transition line-clamp-2 break-words"
            >
              {job.title}
            </Link>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <Globe2 className="h-3.5 w-3.5" /> {job.location_raw || job.country}
              </span>
              <span className="px-2 py-0.5 rounded bg-muted text-foreground font-medium capitalize">
                {job.work_mode}
              </span>
              <span>{job.employment_type}</span>
              {job.experience_level && <span>• {job.experience_level}</span>}
              {job.salary_raw && (
                <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                  • {job.salary_raw}
                </span>
              )}
            </div>
          </div>
        </div>

        <ScoreRing score={match.overall_score} />
      </div>

      {/* Skills & Source Metadata */}
      <div className="flex flex-wrap items-center gap-1.5">
        {match.matched_skills.slice(0, 6).map((sk) => (
          <span
            key={sk}
            className="text-[11px] px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20"
          >
            ✓ {sk}
          </span>
        ))}
        {match.missing_mandatory_skills.slice(0, 3).map((sk) => (
          <span
            key={sk}
            className="text-[11px] px-2 py-0.5 rounded-md bg-rose-500/10 text-rose-600 dark:text-rose-300 border border-rose-500/20"
          >
            Missing: {sk}
          </span>
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-border text-xs text-muted-foreground">
        <div className="flex flex-wrap items-center gap-3">
          <span>
            Source: <strong className="text-foreground">{job.source_name}</strong>
          </span>
          {job.published_at && (
            <span className="inline-flex items-center gap-1">
              <Calendar className="h-3.5 w-3.5" /> Published {formatDate(job.published_at)}
            </span>
          )}
          {job.application_deadline && (
            <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400">
              <Clock className="h-3.5 w-3.5" /> Deadline {formatDate(job.application_deadline)}
            </span>
          )}
        </div>

        {/* All 7 Required Job Card Actions */}
        <div className="flex flex-wrap items-center gap-1.5">
          <Link
            href={`/jobs/${job.id}`}
            className="px-2.5 py-1.5 rounded-lg border border-border hover:bg-accent text-foreground font-medium transition"
          >
            Details & Match Analysis
          </Link>

          <a
            href={job.apply_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground font-medium hover:opacity-90 transition"
          >
            Apply Now <ExternalLink className="h-3 w-3" />
          </a>

          <button
            onClick={() => onToggleSave(job.id, match.is_saved)}
            className={cn(
              "inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border transition font-medium",
              match.is_saved
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-border hover:bg-accent text-foreground"
            )}
            title="Save Job"
          >
            {match.is_saved ? <BookmarkCheck className="h-3.5 w-3.5" /> : <Bookmark className="h-3.5 w-3.5" />}
            {match.is_saved ? "Saved" : "Save"}
          </button>

          <button
            onClick={() => onToggleCompare(job.id)}
            className={cn(
              "inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border transition font-medium",
              isCompared
                ? "border-primary bg-primary/15 text-primary"
                : "border-border hover:bg-accent text-foreground"
            )}
            title="Add to Job Comparison"
          >
            <GitCompare className="h-3.5 w-3.5" />
            {isCompared ? "Comparing" : "Compare"}
          </button>

          <button
            onClick={() => onMarkApplied(job.id)}
            className={cn(
              "inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border transition font-medium",
              match.application_status === "applied"
                ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                : "border-border hover:bg-accent text-foreground"
            )}
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            {match.application_status ? match.application_status.toUpperCase() : "Mark Applied"}
          </button>

          <Link
            href={`/assistant?job_id=${job.id}`}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-border hover:bg-accent text-foreground font-medium transition"
            title="Open in AI Career Assistant"
          >
            <Sparkles className="h-3.5 w-3.5 text-primary" />
          </Link>

          <button
            onClick={() => onHide(job.id)}
            className="p-1.5 rounded-lg border border-border hover:bg-rose-500/10 hover:text-rose-500 transition"
            title="Hide Job"
          >
            <EyeOff className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
