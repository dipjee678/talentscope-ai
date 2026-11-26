"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Compass, Rocket, Sliders } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { apiFetch } from "@/lib/api";
import type { JobSourceInfo, UploadedCV } from "@/lib/types";
import { POPULAR_COUNTRIES, cn } from "@/lib/utils";

export default function NewSearchPage() {
  const router = useRouter();
  const [cvs, setCvs] = useState<UploadedCV[]>([]);
  const [sources, setSources] = useState<JobSourceInfo[]>([]);
  const [selectedCvId, setSelectedCvId] = useState("");
  const [selectedCountries, setSelectedCountries] = useState<string[]>(["Worldwide"]);
  const [customCountry, setCustomCountry] = useState("");
  const [minMatch, setMinMatch] = useState(50);

  // Optional filters
  const [jobCategory, setJobCategory] = useState("");
  const [industry, setIndustry] = useState("");
  const [experienceLevel, setExperienceLevel] = useState("");
  const [employmentType, setEmploymentType] = useState("");
  const [workModes, setWorkModes] = useState<string[]>([]);
  const [visaOnly, setVisaOnly] = useState(false);
  const [englishOnly, setEnglishOnly] = useState(false);
  const [freshGrad, setFreshGrad] = useState(false);
  const [internship, setInternship] = useState(false);
  const [entryLevel, setEntryLevel] = useState(false);
  const [showAdvancedWeights, setShowAdvancedWeights] = useState(false);
  const [weights, setWeights] = useState({
    technical_skills: 30,
    education: 15,
    work_experience: 20,
    required_qualifications: 15,
    projects_achievements: 10,
    role_relevance: 10
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([apiFetch<UploadedCV[]>("/cvs"), apiFetch<JobSourceInfo[]>("/sources")])
      .then(([cvList, srcList]) => {
        setCvs(cvList);
        const active = cvList.find((c) => c.is_active) || cvList[0];
        if (active) setSelectedCvId(active.id);
        setSources(srcList);
      })
      .catch((err) => setError(err.message));
  }, []);

  const toggleCountry = (c: string) => {
    setSelectedCountries((prev) =>
      prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]
    );
  };

  const addCustomCountry = () => {
    const clean = customCountry.trim();
    if (clean && !selectedCountries.includes(clean)) {
      setSelectedCountries((prev) => [...prev, clean]);
      setCustomCountry("");
    }
  };

  const toggleMode = (m: string) => {
    setWorkModes((prev) => (prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]));
  };

  const handleStartSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCvId) {
      setError("Please upload and select a CV first.");
      return;
    }
    if (selectedCountries.length === 0) {
      setError("Please select at least one target country.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const session = await apiFetch<{ id: string }>("/searches", {
        method: "POST",
        body: JSON.stringify({
          cv_id: selectedCvId,
          target_countries: selectedCountries,
          min_match_score: minMatch,
          job_categories: jobCategory ? [jobCategory] : [],
          industries: industry ? [industry] : [],
          experience_levels: experienceLevel ? [experienceLevel] : [],
          employment_types: employmentType ? [employmentType] : [],
          work_modes: workModes,
          visa_sponsorship_only: visaOnly,
          english_only: englishOnly,
          fresh_graduate: freshGrad,
          internship,
          entry_level: entryLevel,
          matching_weights: weights
        })
      });
      router.push(`/search/${session.id}`);
    } catch (err: any) {
      setError(err.message || "Could not start AI job search.");
      setSubmitting(false);
    }
  };

  return (
    <AppShell>
      <div className="max-w-4xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Compass className="h-6 w-6 text-primary" /> Configure Autonomous AI Job Search
          </h1>
          <p className="text-sm text-muted-foreground">
            Only CV, target country, and minimum match percentage are required. Optional preferences refine query
            synthesis and ranking.
          </p>
        </div>

        {cvs.length === 0 ? (
          <div className="rounded-xl border border-border bg-card p-8 text-center space-y-3">
            <p className="text-sm text-muted-foreground">
              You need at least one uploaded CV before starting an autonomous search.
            </p>
            <Link
              href="/cv/upload"
              className="inline-block px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-semibold"
            >
              Upload CV Now →
            </Link>
          </div>
        ) : (
          <form onSubmit={handleStartSearch} className="space-y-6">
            {error && (
              <div className="p-3 rounded-lg border border-rose-500/30 bg-rose-500/10 text-xs text-rose-500">
                {error}
              </div>
            )}

            {/* Required Fields Card */}
            <div className="rounded-xl border border-border bg-card p-6 space-y-5">
              <div className="text-xs font-semibold uppercase tracking-wider text-primary">
                Required Search Parameters
              </div>

              <div>
                <label className="text-xs font-medium">1. Select Candidate CV</label>
                <select
                  value={selectedCvId}
                  onChange={(e) => setSelectedCvId(e.target.value)}
                  className="mt-1.5 w-full px-3.5 py-2.5 rounded-lg border border-border bg-background text-sm"
                >
                  {cvs.map((cv) => (
                    <option key={cv.id} value={cv.id}>
                      {cv.original_filename} (v{cv.version_number}{cv.is_active ? " — Active" : ""})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-medium">
                  2. Target Country / Countries ({selectedCountries.length} selected)
                </label>
                <div className="mt-2 flex flex-wrap gap-2">
                  {POPULAR_COUNTRIES.map((c) => {
                    const active = selectedCountries.includes(c);
                    return (
                      <button
                        type="button"
                        key={c}
                        onClick={() => toggleCountry(c)}
                        className={cn(
                          "px-3 py-1.5 rounded-lg text-xs font-medium border transition",
                          active
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-border bg-background hover:bg-accent"
                        )}
                      >
                        {c}
                      </button>
                    );
                  })}
                </div>
                <div className="mt-2.5 flex items-center gap-2 max-w-sm">
                  <input
                    value={customCountry}
                    onChange={(e) => setCustomCountry(e.target.value)}
                    placeholder="Add another country..."
                    className="flex-1 px-3 py-1.5 rounded-lg border border-border bg-background text-xs"
                  />
                  <button
                    type="button"
                    onClick={addCustomCountry}
                    className="px-3 py-1.5 rounded-lg border border-border hover:bg-accent text-xs font-medium"
                  >
                    Add
                  </button>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium">3. Minimum CV Matching Percentage</label>
                  <span className="text-sm font-bold text-primary">{minMatch}%</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={1}
                  value={minMatch}
                  onChange={(e) => setMinMatch(Number(e.target.value))}
                  className="mt-2 w-full accent-primary"
                />
                <div className="flex justify-between text-[11px] text-muted-foreground">
                  <span>0% (Broadest exploration)</span>
                  <span>50% (Balanced fit)</span>
                  <span>80%+ (Strict alignment)</span>
                </div>
              </div>
            </div>

            {/* Optional Preferences Card */}
            <div className="rounded-xl border border-border bg-card p-6 space-y-5">
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Optional Filters & Preferences
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium">Job Category (optional)</label>
                  <input
                    value={jobCategory}
                    onChange={(e) => setJobCategory(e.target.value)}
                    placeholder="e.g. Software Engineering, Data Science"
                    className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium">Industry (optional)</label>
                  <input
                    value={industry}
                    onChange={(e) => setIndustry(e.target.value)}
                    placeholder="e.g. FinTech, AI, Cloud, Healthcare"
                    className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium">Experience Level (optional)</label>
                  <select
                    value={experienceLevel}
                    onChange={(e) => setExperienceLevel(e.target.value)}
                    className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                  >
                    <option value="">Any level</option>
                    <option value="Internship">Internship</option>
                    <option value="Entry-Level">Entry-Level</option>
                    <option value="Mid-Level">Mid-Level</option>
                    <option value="Senior">Senior</option>
                    <option value="Lead / Principal">Lead / Principal</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium">Employment Type (optional)</label>
                  <select
                    value={employmentType}
                    onChange={(e) => setEmploymentType(e.target.value)}
                    className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                  >
                    <option value="">Any type</option>
                    <option value="Full-time">Full-time</option>
                    <option value="Part-time">Part-time</option>
                    <option value="Contract">Contract</option>
                    <option value="Internship">Internship</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs font-medium block mb-2">Work Mode</label>
                <div className="flex flex-wrap gap-2">
                  {["remote", "hybrid", "onsite"].map((m) => (
                    <button
                      type="button"
                      key={m}
                      onClick={() => toggleMode(m)}
                      className={cn(
                        "px-3.5 py-1.5 rounded-lg border text-xs font-medium capitalize transition",
                        workModes.includes(m)
                          ? "border-primary bg-primary/15 text-primary"
                          : "border-border hover:bg-accent"
                      )}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
                {[
                  { label: "Visa sponsorship preferred", val: visaOnly, set: setVisaOnly },
                  { label: "English-speaking jobs", val: englishOnly, set: setEnglishOnly },
                  { label: "Fresh graduate opportunities", val: freshGrad, set: setFreshGrad },
                  { label: "Internship opportunities", val: internship, set: setInternship },
                  { label: "Entry-level positions", val: entryLevel, set: setEntryLevel }
                ].map((opt) => (
                  <label
                    key={opt.label}
                    className="flex items-center gap-2 p-2.5 rounded-lg border border-border cursor-pointer hover:bg-accent/50"
                  >
                    <input
                      type="checkbox"
                      checked={opt.val}
                      onChange={(e) => opt.set(e.target.checked)}
                      className="accent-primary"
                    />
                    <span>{opt.label}</span>
                  </label>
                ))}
              </div>

              {/* Configurable 6-Dimension Weights */}
              <div className="pt-2 border-t border-border">
                <button
                  type="button"
                  onClick={() => setShowAdvancedWeights(!showAdvancedWeights)}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
                >
                  <Sliders className="h-3.5 w-3.5" />
                  {showAdvancedWeights
                    ? "Hide Scoring Weights & Source Coverage"
                    : "Customize 6-Dimension Matching Weights & View Active Sources"}
                </button>

                {showAdvancedWeights && (
                  <div className="mt-4 space-y-4">
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                      {Object.entries(weights).map(([k, v]) => (
                        <div key={k} className="p-2.5 rounded-lg border border-border bg-background">
                          <label className="text-[11px] font-medium capitalize block">
                            {k.replace(/_/g, " ")} (%)
                          </label>
                          <input
                            type="number"
                            min={0}
                            max={100}
                            value={v}
                            onChange={(e) =>
                              setWeights((prev) => ({ ...prev, [k]: Number(e.target.value) }))
                            }
                            className="mt-1 w-full px-2 py-1 rounded border border-border bg-card text-xs"
                          />
                        </div>
                      ))}
                    </div>

                    <div className="text-xs text-muted-foreground">
                      <strong className="text-foreground">
                        {sources.filter((s) => s.api_key_configured).length} of {sources.length}
                      </strong>{" "}
                      registered job-source integrations are active right now (open APIs + direct Greenhouse/Lever/Ashby
                      career pages; optional keyed connectors can be enabled anytime in <code>.env</code>).
                    </div>
                  </div>
                )}
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-xl bg-primary text-primary-foreground font-semibold shadow-sm hover:opacity-90 disabled:opacity-50 transition"
            >
              <Rocket className="h-4 w-4" />
              {submitting ? "Launching 7-Agent Pipeline..." : "Start AI Job Search"}
            </button>
          </form>
        )}
      </div>
    </AppShell>
  );
}
