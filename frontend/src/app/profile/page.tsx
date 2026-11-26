"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, CheckCircle2, Save } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { apiFetch } from "@/lib/api";
import type { CandidateProfile } from "@/lib/types";

function splitCsv(val: string): string[] {
  return val
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function CandidateProfilePage() {
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Editable form state
  const [fullName, setFullName] = useState("");
  const [headline, setHeadline] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [location, setLocation] = useState("");
  const [summary, setSummary] = useState("");
  const [yearsExp, setYearsExp] = useState("");
  const [highestDegree, setHighestDegree] = useState("");
  const [universities, setUniversities] = useState("");
  const [progLangs, setProgLangs] = useState("");
  const [techSkills, setTechSkills] = useState("");
  const [softSkills, setSoftSkills] = useState("");
  const [certifications, setCertifications] = useState("");
  const [spokenLangs, setSpokenLangs] = useState("");
  const [careerInterests, setCareerInterests] = useState("");
  const [achievements, setAchievements] = useState("");

  useEffect(() => {
    apiFetch<CandidateProfile>("/profiles/active")
      .then((p) => {
        setProfile(p);
        setFullName(p.full_name || "");
        setHeadline(p.headline || "");
        setEmail(p.email || "");
        setPhone(p.phone || "");
        setLocation(p.location || "");
        setSummary(p.summary || "");
        setYearsExp(p.years_of_experience != null ? String(p.years_of_experience) : "");
        setHighestDegree(p.highest_degree || "");
        setUniversities(p.universities.join(", "));
        setProgLangs(p.programming_languages.join(", "));
        setTechSkills(p.technical_skills.join(", "));
        setSoftSkills(p.soft_skills.join(", "));
        setCertifications(p.certifications.join(", "));
        setSpokenLangs(p.spoken_languages.join(", "));
        setCareerInterests(p.career_interests.join(", "));
        setAchievements(p.achievements.join(", "));
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile) return;
    setSaving(true);
    setSavedMsg(null);
    setError(null);
    try {
      const updated = await apiFetch<CandidateProfile>(`/profiles/${profile.id}`, {
        method: "PUT",
        body: JSON.stringify({
          full_name: fullName || null,
          headline: headline || null,
          email: email || null,
          phone: phone || null,
          location: location || null,
          summary: summary || null,
          years_of_experience: yearsExp !== "" ? Number(yearsExp) : null,
          highest_degree: highestDegree || null,
          universities: splitCsv(universities),
          programming_languages: splitCsv(progLangs),
          technical_skills: splitCsv(techSkills),
          soft_skills: splitCsv(softSkills),
          certifications: splitCsv(certifications),
          spoken_languages: splitCsv(spokenLangs),
          career_interests: splitCsv(careerInterests),
          achievements: splitCsv(achievements)
        })
      });
      setProfile(updated);
      setSavedMsg("Profile saved and semantic matching vector updated.");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell>
      <div className="max-w-4xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Structured Candidate Profile</h1>
            <p className="text-sm text-muted-foreground">
              Review and refine information extracted from your active CV before running AI job matching.
            </p>
          </div>
          <Link
            href="/search/new"
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:opacity-90"
          >
            Start AI Job Search →
          </Link>
        </div>

        {loading ? (
          <div className="h-64 rounded-xl border border-border bg-card animate-pulse" />
        ) : !profile ? (
          <div className="rounded-xl border border-border bg-card p-8 text-center space-y-3">
            <p className="text-sm text-muted-foreground">{error || "No active CV profile found."}</p>
            <Link
              href="/cv/upload"
              className="inline-block px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-semibold"
            >
              Upload Your CV
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSave} className="space-y-6">
            {profile.missing_or_unclear.length > 0 && (
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-700 dark:text-amber-300 space-y-1">
                <div className="font-semibold flex items-center gap-1.5">
                  <AlertCircle className="h-4 w-4" /> Missing or Unclear CV Details Identified by Agent 1:
                </div>
                {profile.missing_or_unclear.map((m, idx) => (
                  <div key={idx}>• {m}</div>
                ))}
              </div>
            )}

            {savedMsg && (
              <div className="p-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4" /> {savedMsg}
              </div>
            )}

            <div className="rounded-xl border border-border bg-card p-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium">Full Name</label>
                <input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-medium">Professional Headline</label>
                <input
                  value={headline}
                  onChange={(e) => setHeadline(e.target.value)}
                  placeholder="e.g. Full-Stack & Machine Learning Engineer"
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-medium">Email</label>
                <input
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-medium">Phone</label>
                <input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-medium">Current Location</label>
                <input
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="City, Country"
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-medium">Years of Experience</label>
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  max="50"
                  value={yearsExp}
                  onChange={(e) => setYearsExp(e.target.value)}
                  placeholder="e.g. 2"
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-medium">Highest Academic Qualification</label>
                <input
                  value={highestDegree}
                  onChange={(e) => setHighestDegree(e.target.value)}
                  placeholder="e.g. Bachelor's Degree in Computer Science"
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-medium">Universities (comma-separated)</label>
                <input
                  value={universities}
                  onChange={(e) => setUniversities(e.target.value)}
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="text-xs font-medium">Professional Summary</label>
                <textarea
                  rows={3}
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                />
              </div>
            </div>

            <div className="rounded-xl border border-border bg-card p-6 space-y-4">
              <h2 className="font-semibold text-base">Skills, Languages & Career Interests (comma-separated)</h2>
              <div>
                <label className="text-xs font-medium">Programming Languages</label>
                <input
                  value={progLangs}
                  onChange={(e) => setProgLangs(e.target.value)}
                  placeholder="Python, TypeScript, SQL, C++"
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-medium">Technical Skills, Frameworks & Cloud</label>
                <input
                  value={techSkills}
                  onChange={(e) => setTechSkills(e.target.value)}
                  placeholder="FastAPI, React, Next.js, PostgreSQL, Machine Learning, Docker"
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium">Soft Skills</label>
                  <input
                    value={softSkills}
                    onChange={(e) => setSoftSkills(e.target.value)}
                    className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium">Spoken Languages</label>
                  <input
                    value={spokenLangs}
                    onChange={(e) => setSpokenLangs(e.target.value)}
                    placeholder="English, German"
                    className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium">Certifications</label>
                  <input
                    value={certifications}
                    onChange={(e) => setCertifications(e.target.value)}
                    className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium">Career Interests / Target Roles</label>
                  <input
                    value={careerInterests}
                    onChange={(e) => setCareerInterests(e.target.value)}
                    placeholder="Backend Engineer, AI Engineer"
                    className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium">Relevant Achievements</label>
                <input
                  value={achievements}
                  onChange={(e) => setAchievements(e.target.value)}
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-border bg-background text-sm"
                />
              </div>
            </div>

            {/* Extracted Experience, Internships & Projects Readout */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                { label: "Professional Experience", items: profile.experience },
                { label: "Internships", items: profile.internships },
                { label: "Academic & Personal Projects", items: profile.projects }
              ].map((sec) => (
                <div key={sec.label} className="rounded-xl border border-border bg-card p-4 space-y-2">
                  <h3 className="font-semibold text-xs uppercase tracking-wider text-muted-foreground">
                    {sec.label} ({sec.items.length})
                  </h3>
                  {sec.items.length === 0 ? (
                    <p className="text-xs text-muted-foreground">None detected on CV.</p>
                  ) : (
                    <div className="space-y-2 text-xs">
                      {sec.items.map((it, idx) => (
                        <div key={idx} className="p-2 rounded bg-muted/50">
                          <div className="font-medium">{it.title}</div>
                          {it.highlights?.slice(0, 2).map((h, hIdx) => (
                            <div key={hIdx} className="text-muted-foreground mt-0.5">
                              • {h}
                            </div>
                          ))}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>

            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-semibold hover:opacity-90 disabled:opacity-50"
            >
              <Save className="h-4 w-4" /> {saving ? "Saving..." : "Save Verified Profile Changes"}
            </button>
          </form>
        )}
      </div>
    </AppShell>
  );
}
