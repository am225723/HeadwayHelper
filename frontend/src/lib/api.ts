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
    throw new Error(error.detail || "Request failed");
  }
  return response.json();
}
