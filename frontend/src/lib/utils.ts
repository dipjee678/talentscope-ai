import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso?: string | null): string {
  if (!iso) return "Not specified";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Not specified";
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric"
  });
}

const HUMAN_LABELS: Record<string, string> = {
  not_needed: "Not needed",
  manual_review_needed: "Needs review",
  clean: "Passed",
  completed: "Completed",
  running: "Running",
  queued: "Queued",
  failed: "Failed",
  cancelled: "Cancelled",
  cv_verification: "Reading your CV",
  discovering_jobs: "Searching job boards",
  discovery_complete: "Jobs found",
  extraction_complete: "Reading job requirements",
  verification_complete: "Checking links & removing duplicates",
  matching_complete: "Scoring each job against your CV",
  ranking_complete: "Ranking the best fits",
  onsite: "On-site",
  hybrid: "Hybrid",
  remote: "Remote"
};

/** Turn backend codes like "manual_review_needed" into readable text. */
export function humanize(value?: string | null): string {
  if (!value) return "";
  if (HUMAN_LABELS[value]) return HUMAN_LABELS[value];
  const spaced = value.replace(/[_-]+/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export const POPULAR_COUNTRIES = [
  "Worldwide",
  "United States",
  "United Kingdom",
  "Germany",
  "Canada",
  "Australia",
  "Netherlands",
  "Sweden",
  "France",
  "Switzerland",
  "Ireland",
  "Singapore",
  "India",
  "Bangladesh",
  "United Arab Emirates",
  "Spain",
  "Poland",
  "Japan"
];
