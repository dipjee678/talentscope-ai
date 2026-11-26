"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Filter, GitCompare, Info, Search } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { JobCard } from "@/components/job-card";
import { useApp } from "@/components/providers";
import { apiFetch } from "@/lib/api";
import type { JobMatch } from "@/lib/types";

function JobResultsContent() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session_id") || "";
  const { compareIds, toggleCompareId } = useApp();

  const [matches, setMatches] = useState<JobMatch[]>([]);
  const [loading, setLoading] = useState(true);

  const [searchQuery, setSearchQuery] = useState("");
  const [country, setCountry] = useState("");
  const [city, setCity] = useState("");
  const [company, setCompany] = useState("");
  const [industry, setIndustry] = useState("");
  const [category, setCategory] = useState("");
  const [minScore, setMinScore] = useState("");
  const [workMode, setWorkMode] = useState("");
  const [experienceLevel, setExperienceLevel] = useState("");
  const [employmentType, setEmploymentType] = useState("");
  const [salaryMin, setSalaryMin] = useState("");
  const [visaOnly, setVisaOnly] = useState(false);
  const [publishedDays, setPublishedDays] = useState("");
  const [hasDeadline, setHasDeadline] = useState(false);
  const [sortBy, setSortBy] = useState("highest_match");
  const [showFilters, setShowFilters] = useState(false);

  const loadJobs = async () => {
    setLoading(true);
    try {
      const qs = new URLSearchParams();
      if (sessionId) qs.set("session_id", sessionId);
      if (searchQuery) qs.set("search_query", searchQuery);
      if (country) qs.set("country", country);
      if (city) qs.set("city", city);
      if (company) qs.set("company", company);
      if (industry) qs.set("industry", industry);
      if (category) qs.set("category", category);
      if (minScore) qs.set("min_score", minScore);
      if (workMode) qs.set("work_mode", workMode);
      if (experienceLevel) qs.set("experience_level", experienceLevel);
      if (employmentType) qs.set("employment_type", employmentType);
      if (salaryMin) qs.set("salary_min", salaryMin);
      if (visaOnly) qs.set("visa_sponsorship", "true");
      if (publishedDays) qs.set("published_within_days", publishedDays);
      if (hasDeadline) qs.set("has_deadline", "true");
      qs.set("sort_by", sortBy);

      const list = await apiFetch<JobMatch[]>(`/jobs?${qs.toString()}`);
      setMatches(list);
    } catch {
      setMatches([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, [sessionId, sortBy, workMode, experienceLevel, employmentType, visaOnly, publishedDays, hasDeadline]);

  const handleToggleSave = async (jobId: string, currentlySaved: boolean) => {
    if (currentlySaved) {
      await apiFetch(`/tracker/saved/${jobId}`, { method: "DELETE" });
    } else {
      await apiFetch("/tracker/saved", {
        method: "POST",
        body: JSON.stringify({ job_id: jobId })
      });
    }
    setMatches((prev) =>
      prev.map((m) => (m.job_id === jobId ? { ...m, is_saved: !currentlySaved } : m))
    );
  };

  const handleMarkApplied = async (jobId: string) => {
    await apiFetch("/tracker/applications", {
      method: "POST",
      body: JSON.stringify({ job_id: jobId, status: "applied" })
    });
    setMatches((prev) =>
      prev.map((m) => (m.job_id === jobId ? { ...m, application_status: "applied" } : m))
    );
  };

  const handleHide = async (jobId: string) => {
    await apiFetch(`/jobs/${jobId}/hide?hide=true`, { method: "POST" });
    setMatches((prev) => prev.filter((m) => m.job_id !== jobId));
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Matched Jobs</h1>
          <p className="text-xs text-muted-foreground flex items-center gap-1.5 mt-1">
            <Info className="h-3.5 w-3.5 text-primary shrink-0" />
            Scores show how well your CV fits each job&apos;s requirements (Strong ≥ 75%, Good ≥ 60%). Open
            &ldquo;Details&rdquo; to see exactly why. A score is not a guarantee of an interview.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {compareIds.length >= 2 && (
            <Link
              href="/jobs/compare"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-semibold"
            >
              <GitCompare className="h-4 w-4" /> Compare Selected ({compareIds.length})
            </Link>
          )}
          <Link
            href="/search/new"
            className="px-3.5 py-2 rounded-lg border border-border bg-card text-xs font-medium hover:bg-accent"
          >
            + New AI Search
          </Link>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-4 space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex-1 min-w-[220px] relative">
            <Search className="h-4 w-4 text-muted-foreground absolute left-3 top-2.5" />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && loadJobs()}
              placeholder="Search title, company, or keywords..."
              className="w-full pl-9 pr-3 py-2 rounded-lg border border-border bg-background text-sm"
            />
          </div>

          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="px-3 py-2 rounded-lg border border-border bg-background text-sm"
          >
            <option value="highest_match">Sort: Highest Matching %</option>
            <option value="most_relevant">Sort: Most Relevant</option>
            <option value="latest_published">Sort: Latest Published</option>
            <option value="highest_salary">Sort: Highest Salary</option>
            <option value="company_name">Sort: Company Name (A–Z)</option>
          </select>

          <button
            onClick={() => setShowFilters(!showFilters)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-border hover:bg-accent text-sm font-medium"
          >
            <Filter className="h-4 w-4" /> Advanced Filters
          </button>

          <button
            onClick={loadJobs}
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-semibold"
          >
            Apply
          </button>
        </div>

        {showFilters && (
          <div className="pt-3 border-t border-border grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
            <input
              placeholder="Country (e.g. Germany)"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              className="px-3 py-2 rounded-lg border border-border bg-background"
            />
            <input
              placeholder="City (e.g. Berlin, London)"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              className="px-3 py-2 rounded-lg border border-border bg-background"
            />
            <input
              placeholder="Company"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              className="px-3 py-2 rounded-lg border border-border bg-background"
            />
            <input
              placeholder="Industry"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              className="px-3 py-2 rounded-lg border border-border bg-background"
            />
            <input
              placeholder="Job Category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="px-3 py-2 rounded-lg border border-border bg-background"
            />
            <input
              type="number"
              placeholder="Min Match % (0-100)"
              value={minScore}
              onChange={(e) => setMinScore(e.target.value)}
              className="px-3 py-2 rounded-lg border border-border bg-background"
            />
            <input
              type="number"
              placeholder="Min Annual Salary"
              value={salaryMin}
              onChange={(e) => setSalaryMin(e.target.value)}
              className="px-3 py-2 rounded-lg border border-border bg-background"
            />
            <select
              value={workMode}
              onChange={(e) => setWorkMode(e.target.value)}
              className="px-3 py-2 rounded-lg border border-border bg-background"
            >
              <option value="">Any Work Mode</option>
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">Onsite</option>
            </select>
            <select
              value={experienceLevel}
              onChange={(e) => setExperienceLevel(e.target.value)}
              className="px-3 py-2 rounded-lg border border-border bg-background"
            >
              <option value="">Any Experience Level</option>
              <option value="Internship">Internship</option>
              <option value="Entry-Level">Entry-Level</option>
              <option value="Mid-Level">Mid-Level</option>
              <option value="Senior">Senior</option>
              <option value="Lead / Principal">Lead / Principal</option>
            </select>
            <select
              value={employmentType}
              onChange={(e) => setEmploymentType(e.target.value)}
              className="px-3 py-2 rounded-lg border border-border bg-background"
            >
              <option value="">Any Employment Type</option>
              <option value="Full-time">Full-time</option>
              <option value="Part-time">Part-time</option>
              <option value="Contract">Contract</option>
              <option value="Internship">Internship</option>
            </select>
            <select
              value={publishedDays}
              onChange={(e) => setPublishedDays(e.target.value)}
              className="px-3 py-2 rounded-lg border border-border bg-background"
            >
              <option value="">Any Publication Date</option>
              <option value="3">Last 3 days</option>
              <option value="7">Last 7 days</option>
              <option value="14">Last 14 days</option>
              <option value="30">Last 30 days</option>
            </select>
            <div className="flex items-center gap-3 px-1">
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={visaOnly}
                  onChange={(e) => setVisaOnly(e.target.checked)}
                  className="accent-primary"
                />
                Visa Sponsors
              </label>
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={hasDeadline}
                  onChange={(e) => setHasDeadline(e.target.checked)}
                  className="accent-primary"
                />
                Has Deadline
              </label>
            </div>
          </div>
        )}
      </div>

      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-44 rounded-xl border border-border bg-card animate-pulse" />
          ))}
        </div>
      ) : matches.length === 0 ? (
        <div className="rounded-xl border border-border bg-card p-12 text-center space-y-3">
          <div className="font-semibold text-base">No matching job opportunities found for current filters</div>
          <p className="text-xs text-muted-foreground max-w-md mx-auto">
            Try lowering your minimum matching percentage, broadening target countries, or initiating a fresh AI
            search session.
          </p>
          <Link
            href="/search/new"
            className="inline-block px-4 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-semibold"
          >
            Start New AI Search →
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="text-xs text-muted-foreground">
            Showing <strong className="text-foreground">{matches.length}</strong> qualifying opportunities
          </div>
          {matches.map((m) => (
            <JobCard
              key={m.id}
              match={m}
              isCompared={compareIds.includes(m.job_id)}
              onToggleCompare={toggleCompareId}
              onToggleSave={handleToggleSave}
              onMarkApplied={handleMarkApplied}
              onHide={handleHide}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function JobResultsPage() {
  return (
    <AppShell>
      <Suspense fallback={<div className="p-8 text-sm text-muted-foreground">Loading job results...</div>}>
        <JobResultsContent />
      </Suspense>
    </AppShell>
  );
}
