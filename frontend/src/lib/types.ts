/**
 * TypeScript interfaces mirroring backend Pydantic models
 * Keep in sync with backend/core/models/ and backend/db/models.py
 */

// ============================================================================
// Core Enums and Literals
// ============================================================================

export type Band = "XS" | "S" | "M" | "L" | "XL";
export type ComplexityClass = "XS" | "S" | "M" | "L" | "XL";
export type InputSource =
  | "ai_extracted"
  | "manual"
  | "corrected"
  | "from_s1"
  | "from_s2"
  | "from_s3"
  | "imported";

export type StageId = "s1" | "s2" | "s3" | "s4";
export type StageRunStatus = "running" | "complete" | "failed";
export type ReadinessStatus =
  | "complete"
  | "stale"
  | "running"
  | "ready"
  | "not_ready"
  | "failed";

export type MigrationDecision =
  | "QUICK_WIN"
  | "STRATEGIC"
  | "HOLD"
  | "DO_NOT_MIGRATE";
export type Confidence = "HIGH" | "MEDIUM" | "LOW";

export type UserRole = "user" | "superuser";

// ============================================================================
// User & Auth
// ============================================================================

export interface User {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// ============================================================================
// Project & UseCase
// ============================================================================

export interface Project {
  id: string;
  name: string;
  description?: string;
  created_by?: string;
  use_case_count?: number;
  created_at: string;
  updated_at?: string;
  use_cases?: UseCase[];
}

export interface UseCase {
  id: string;
  project_id: string;
  name: string;
  description?: string;
  source_platform?: string;
  install_status?: string;
  custom_fields: Record<string, unknown>;
  s1_inputs: Record<string, unknown>;
  s1_latest_run_id?: string;
  s2_inputs: Record<string, unknown>;
  s2_latest_run_id?: string;
  s3_inputs: Record<string, unknown>;
  s3_latest_run_id?: string;
  s4_inputs: Record<string, unknown>;
  s4_latest_run_id?: string;
  created_at: string;
  updated_at?: string;
}

// ============================================================================
// Stage Runs
// ============================================================================

export interface StageRun {
  id: string;
  use_case_id: string;
  stage: StageId;
  run_number: number;
  inputs_snapshot: Record<string, unknown>;
  inputs_hash: string;
  result: Record<string, unknown>;
  model_used?: string;
  weight_config_snapshot?: Record<string, unknown>;
  prompt_variant_snapshot?: string;
  triggered_by?: string;
  created_at: string;
  status: StageRunStatus;
  error_message?: string;
}

// ============================================================================
// Stage 1 (Assessment)
// ============================================================================

export interface S1Inputs {
  name: string;
  description: string;
  source_platform?: string;
  install_status?: string;
}

export interface S1Result {
  technical_feasibility: number;
  migration_effort: number;
  platform_suitability: number;
  risk: number;
  total_score: number;
  migration_decision: MigrationDecision;
  confidence: Confidence;
  analysis: string;
  blockers: string[];
  power_automate_fit: string;
  follow_up_questions?: string[];
  override_reason: string;
  override_by: string;
}

export interface S1Override {
  field: string;
  value: number | string;
  reason: string;
}

// ============================================================================
// Stage 2 (Complexity)
// ============================================================================

export interface AttributeBands {
  activities: Band;
  business_rules: Band;
  layouts: Band;
  interfaces: Band;
  technology: Band;
}

export interface AttributeBandsWithSource extends AttributeBands {
  activities_source: InputSource;
  business_rules_source: InputSource;
  layouts_source: InputSource;
  interfaces_source: InputSource;
  technology_source: InputSource;
}

export interface S2Inputs {
  bands?: Partial<AttributeBandsWithSource>;
  document_text?: string;
  document_text_source?: InputSource;
}

export interface S2Result {
  total_score: number;
  complexity_class: ComplexityClass;
  effort_min_weeks: number;
  effort_max_weeks: number;
  sprint_min: number;
  sprint_max: number;
  attribute_weights: Record<string, number>;
  bands: AttributeBands;
  extraction_notes?: string;
  process_summary?: {
    key_activities?: string[];
    key_logical_points?: string[];
    key_applications?: string[];
    key_layouts?: string[];
    key_additional_technologies?: string[];
  };
  _assessment_result?: {
    complexity_tier: string;
    confidence_score: number;
    reasoning: string;
    requires_tech_lead_review: boolean;
  };
}

// ============================================================================
// Stage 3 (Timeline)
// ============================================================================

export interface Phase {
  name: string;
  start_date: string;
  end_date: string;
  weeks: number;
  is_delta?: boolean;
}

export interface S3Inputs {
  effort_weeks: number;
  start_date: string;
  complexity_class: ComplexityClass;
  phase_deltas?: Record<string, number>;
}

export interface S3Result {
  phases: Phase[];
  narrative?: string;
}

// ============================================================================
// Stage 4 (Sprint Tracker)
// ============================================================================

export interface Feature {
  name: string;
  description: string;
  size: Band;
  dependencies: string[];
}

export interface SprintPlan {
  feature: Feature;
  sprint_number: number;
}

export interface S4Inputs {
  sprint_count: number;
  sprint_length_weeks: number;
  features_override?: Feature[];
}

export interface S4Result {
  features: Feature[];
  sprint_plan: SprintPlan[];
}

// ============================================================================
// Readiness
// ============================================================================

export interface S3ReadinessDetail {
  phase_calculator: ReadinessStatus;
  task_extraction: ReadinessStatus | string;
}

export interface ReadinessResponse {
  s1: ReadinessStatus;
  s2: ReadinessStatus;
  s3: S3ReadinessDetail;
  s4: ReadinessStatus;
}

// ============================================================================
// Settings
// ============================================================================

export interface WeightConfig {
  id: string;
  project_id: string;
  name: string;
  is_active: boolean;
  config: Record<string, Record<Band, number>>;
  yes_threshold: number;
  created_by?: string;
  created_at: string;
}

export interface PhaseConfig {
  id: string;
  project_id: string;
  is_active: boolean;
  config: Record<string, unknown>;
  sprint_length_weeks: number;
  created_at: string;
}

// ============================================================================
// Bulk Upload
// ============================================================================

export interface ColumnMapping {
  name: string | null;
  description?: string | null;
  source_platform?: string | null;
  install_status?: string | null;
}

export interface BulkUploadResponse {
  upload_id: string;
  filename: string;
  columns: string[];
  preview: Record<string, string>[];
  row_count: number;
}

export interface BulkUploadStatusResponse {
  upload_id: string;
  status: "preview" | "confirmed" | "processing" | "complete" | "failed";
  created_count: number | null;
  assessed_count: number | null;
  total_count: number;
  error: string | null;
}

export interface BulkConfirmResponse {
  upload_id: string;
  status: string;
  job_id: string;
}

export interface LLMConfig {
  id: string;
  stage: string;
  model: string;
  temperature: number;
  max_tokens: number;
  is_active: boolean;
  updated_by?: string;
  updated_at: string;
}

export interface PromptVariant {
  id: string;
  stage: string;
  name: string;
  content: Record<string, unknown>;
  is_active: boolean;
  created_by?: string;
  created_at: string;
}

export interface UploadedFile {
  id: string;
  use_case_id: string;
  stage: StageId;
  original_filename: string;
  stored_path: string;
  file_type: string;
  size_bytes?: number;
  uploaded_by?: string;
  created_at: string;
}

// ============================================================================
// Request/Response Types
// ============================================================================

export interface CreateProjectRequest {
  name: string;
  description?: string;
}

export interface CreateUseCaseRequest {
  name: string;
  description?: string;
  source_platform?: string;
  install_status?: string;
  custom_fields?: Record<string, unknown>;
}

export interface UpdateInputsRequest {
  [key: string]: unknown;
}

export interface TriggerRunRequest {
  triggered_by?: string;
}

export interface BulkUploadPreview {
  columns: string[];
  preview: Record<string, unknown>[];
}

export interface BulkConfirmRequest {
  column_mapping: Record<string, string>;
  rows: Record<string, unknown>[];
}
