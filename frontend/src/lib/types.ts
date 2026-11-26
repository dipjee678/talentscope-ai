export interface CustomATSBoard {
  provider: "greenhouse" | "lever" | "ashby";
  slug: string;
  company_name: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  theme_preference: "light" | "dark" | "system";
  data_retention_days: number;
  default_weights: Record<string, number>;
  custom_ats_boards: CustomATSBoard[];
  created_at: string;
}

export interface CandidateSkill {
  id?: string;
  skill_name: string;
  normalized_name?: string;
  category: string;
  proficiency?: string | null;
  source_section?: string | null;
}

export interface StructuredEntry {
  title: string;
  highlights: string[];
}

export interface CandidateProfile {
  id: string;
  user_id: string;
  cv_id: string;
  full_name?: string | null;
  headline?: string | null;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  summary?: string | null;
  years_of_experience?: number | null;
  highest_degree?: string | null;
  universities: string[];
  education: StructuredEntry[];
  programming_languages: string[];
  technical_skills: string[];
  soft_skills: string[];
  experience: StructuredEntry[];
  internships: StructuredEntry[];
  projects: StructuredEntry[];
  certifications: string[];
  spoken_languages: string[];
  career_interests: string[];
  achievements: string[];
  missing_or_unclear: string[];
  extraction_mode: string;
  manually_edited: boolean;
  skills: CandidateSkill[];
  created_at: string;
  updated_at: string;
}

export interface UploadedCV {
  id: string;
  user_id: string;
  original_filename: string;
  file_extension: string;
  content_type: string;
  file_size_bytes: number;
  version_number: number;
  is_active: boolean;
  parse_status: string;
  ocr_status: string;
  security_scan_status: string;
  security_scan_notes: string[];
  prompt_injection_flags: string[];
  created_at: string;
  profile?: CandidateProfile | null;
}

export interface AgentLog {
  id: string;
  agent_name: string;
  stage: string;
  level: string;
  message: string;
  metrics: Record<string, unknown>;
  duration_ms?: number | null;
  created_at: string;
}

export interface SearchSession {
  id: string;
  user_id: string;
  cv_id: string;
  preference_id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  current_stage: string;
  progress_percent: number;
  config_snapshot: Record<string, any>;
  generated_queries: string[];
  sources_searched_count: number;
  sources_searched: Array<{
    slug: string;
    name: string;
    jobs_found: number;
    pages_fetched: number;
    queries_executed: string[];
    duration_ms: number;
  }>;
  sources_unavailable: Array<{
    slug: string;
    name: string;
    status: string;
    reason: string;
  }>;
  jobs_discovered_count: number;
  jobs_verified_count: number;
  duplicates_removed_count: number;
  expired_removed_count: number;
  below_threshold_count: number;
  jobs_matched_count: number;
  coverage_report: Record<string, any>;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  logs: AgentLog[];
}

export interface JobRequirement {
  requirement_type: string;
  requirement_text: string;
  normalized_key: string;
  is_mandatory: boolean;
  min_years?: number | null;
}

export interface JobListing {
  id: string;
  source_slug: string;
  source_name: string;
  external_id?: string | null;
  title: string;
  company_name: string;
  company_logo_url?: string | null;
  country: string;
  city?: string | null;
  location_raw: string;
  work_mode: string;
  employment_type: string;
  experience_level?: string | null;
  min_experience_years?: number | null;
  required_education?: string | null;
  industry?: string | null;
  category?: string | null;
  salary_min?: number | null;
  salary_max?: number | null;
  salary_currency?: string | null;
  salary_period?: string | null;
  salary_raw?: string | null;
  visa_sponsorship?: boolean | null;
  english_speaking: boolean;
  description_text: string;
  source_url: string;
  apply_url: string;
  is_direct_company_link: boolean;
  published_at?: string | null;
  application_deadline?: string | null;
  verification_status: "verified_active" | "expired" | "broken_link" | "unverified";
  verification_details: Record<string, any>;
  last_verified_at?: string | null;
  alternate_sources: Array<{ source_name: string; source_url: string }>;
  requirements: JobRequirement[];
  created_at: string;
}

export interface JobMatch {
  id: string;
  search_session_id: string;
  job_id: string;
  profile_id: string;
  overall_score: number;
  rank_score: number;
  technical_skills_score: number;
  education_score: number;
  experience_score: number;
  qualifications_score: number;
  projects_score: number;
  role_relevance_score: number;
  weights_used: Record<string, number>;
  matched_skills: string[];
  missing_mandatory_skills: string[];
  missing_preferred_skills: string[];
  unstated_on_cv: string[];
  matching_qualifications: string[];
  experience_compatibility: string;
  education_compatibility: string;
  explicit_disqualifiers: string[];
  score_explanation: string;
  strengths: string[];
  weaknesses: string[];
  calculation_breakdown: Record<string, any>;
  is_hidden: boolean;
  is_saved: boolean;
  application_status?: string | null;
  job: JobListing;
  created_at: string;
}

export interface JobSourceInfo {
  slug: string;
  name: string;
  source_type: string;
  base_url: string;
  requires_api_key: boolean;
  api_key_configured: boolean;
  api_key_env_vars: string[];
  supported_countries: string[];
  is_enabled: boolean;
  rate_limit_rpm: number;
  terms_notes: string;
}

export type ApplicationStatus =
  | "saved"
  | "interested"
  | "applied"
  | "assessment"
  | "interview"
  | "offer"
  | "rejected";

export interface TrackedApplication {
  id: string;
  user_id: string;
  job_id: string;
  status: ApplicationStatus;
  applied_at?: string | null;
  application_url?: string | null;
  notes?: string | null;
  follow_up_at?: string | null;
  history: Array<{ status: string; timestamp: string; note?: string }>;
  match_score?: number | null;
  job: JobListing;
  created_at: string;
  updated_at: string;
}

export interface AssistantResult {
  action: string;
  title: string;
  content_markdown: string;
  highlights: string[];
  grounded_facts_used: Record<string, any>;
  generation_mode: string;
  disclaimer: string;
}
