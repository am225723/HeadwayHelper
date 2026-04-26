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
  role: "ADMIN" | "PROVIDER";
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
  placeholder_style: string;
  cleanup_rules_json: Record<string, unknown>;
  is_active: boolean;
  version: number;
  placeholders: string[];
};

export type TemplatePreview = {
  html: string;
  raw_html: string | null;
  placeholders: string[];
  missing_placeholders: string[];
  unreplaced_placeholders: string[];
  cleanup_warnings: string[];
};

export type AdminConfig = {
  rates: AdminRate[];
  billingRules: AdminRule[];
  serviceTypes: AdminServiceType[];
  classificationRules: AdminClassificationRule[];
  settings: AdminSetting[];
  templates: AdminTemplate[];
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
