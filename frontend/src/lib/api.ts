export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

export type SourceDocument = {
  id: string;
  name: string;
  file_type: string;
  processed: boolean;
  uploaded_at: string;
};

export type OutputDocument = {
  id: string;
  doc_type: string;
  status: string;
  created_at: string;
  content: string;
  structured_data: Record<string, unknown> | null;
};

export type Patient = {
  id: string;
  name: string;
  drive_folder_id: string;
  source_documents: SourceDocument[];
  output_documents: OutputDocument[];
};

export type BillingSummary = {
  id: string;
  cpt_codes: string;
  icd10_codes: string;
  service_name: string;
  psychotherapy_minutes: number;
  headway_block: string;
  reimbursement_notes: { candidates?: { codes: string[]; total: number; payer: string }[] } | null;
};

export type BillingComparison = {
  payer: string;
  option_a_total: number | null;
  option_b_total: number | null;
  difference: number | null;
  option_a_codes: string[];
  option_b_codes: string[];
  recommendation: string;
  reason: string;
};

export type CurrentUser = {
  id: string;
  email: string;
  full_name: string | null;
  role: "ADMIN" | "PROVIDER";
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
};

export type AdminRate = {
  id: string;
  payer_name: string;
  cpt_code: string;
  amount: number;
  is_active: boolean;
  notes: string | null;
};

export type AdminRule = {
  id: string;
  rule_key: string;
  rule_value_json: Record<string, unknown>;
  description: string | null;
};

export type AdminServiceType = {
  id: string;
  name: string;
  is_active: boolean;
  display_order: number;
};

export type AdminClassificationRule = {
  id: string;
  category: string;
  keyword_or_pattern: string;
  is_active: boolean;
};

export type AdminSetting = {
  id: string;
  setting_key: string;
  setting_value_json: Record<string, unknown>;
  description: string | null;
};

export type AdminTemplate = {
  id: string;
  document_type: string;
  template_name: string;
  template_source: string;
  placeholder_style: string;
  cleanup_rules_json: Record<string, unknown>;
  is_active: boolean;
  version: number;
  placeholders: string[];
  placeholder_inventory: TemplatePlaceholder[];
  prompt_placeholder_count: number;
  mustache_placeholder_count: number;
  repeated_placeholder_count: number;
};

export type TemplatePlaceholder = {
  placeholder_type: "mustache" | "ai_prompt";
  machine_key: string;
  prompt_text: string;
  raw_token: string;
  section_name: string | null;
  repeat_count: number;
  is_required: boolean;
  default_missing_behavior: string;
};

export type TemplatePreview = {
  html: string;
  raw_html: string | null;
  placeholders: string[];
  placeholder_inventory: TemplatePlaceholder[];
  missing_placeholders: string[];
  unreplaced_placeholders: string[];
  cleanup_warnings: string[];
  template_id: string | null;
  template_version: number | null;
};

export type AdminUser = CurrentUser;

export type DrivePatientFolder = {
  folder_id: string;
  folder_name: string;
  linked_patient_id: string | null;
  linked_patient_name: string | null;
  file_count: number;
  detected_counts: Record<string, number>;
  has_intake: boolean;
  has_assessments: boolean;
  has_zoom_notes: boolean;
  has_outputs: boolean;
};

export type AdminConfig = {
  rates: AdminRate[];
  billingRules: AdminRule[];
  serviceTypes: AdminServiceType[];
  classificationRules: AdminClassificationRule[];
  settings: AdminSetting[];
  templates: AdminTemplate[];
  users: AdminUser[];
  drivePatients: DrivePatientFolder[];
};

export type HealthStatus = {
  status: string;
  [key: string]: unknown;
};

export type DiagnosticsStatus = {
  app: HealthStatus;
  db: HealthStatus;
  drive: HealthStatus;
  ai: HealthStatus;
  templates: HealthStatus;
};

export async function apiFetch<T>(path: string, token: string | null, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers
    }
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `${response.status} ${response.statusText}` || "Request failed");
  }
  return response.json();
}
