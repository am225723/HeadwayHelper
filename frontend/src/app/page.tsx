"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Activity,
  BadgeCheck,
  Clipboard,
  FilePlus2,
  FileText,
  FolderSync,
  LockKeyhole,
  NotebookPen,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Stethoscope
} from "lucide-react";
import { LoginPanel } from "@/components/login-panel";
import { StatusBadge } from "@/components/status-badge";
import { apiFetch, BillingComparison, BillingSummary, Patient, SourceDocument } from "@/lib/api";

type GenerateFn = (path: string, body: object) => Promise<void>;

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [comparison, setComparison] = useState<BillingComparison[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setToken(localStorage.getItem("clinical-ai-token"));
  }, []);

  async function load(nextToken = token) {
    if (!nextToken) return;
    setError(null);
    try {
      const data = await apiFetch<{ items: Patient[] }>("/patients", nextToken);
      setPatients(data.items);
      if (!selectedId && data.items[0]) setSelectedId(data.items[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load patients");
    }
  }

  useEffect(() => {
    load();
  }, [token]);

  const selected = patients.find((patient) => patient.id === selectedId) || null;
  const filtered = useMemo(() => patients.filter((patient) => patient.name.toLowerCase().includes(query.toLowerCase())), [patients, query]);
  const pendingReviewCount = patients.reduce((count, patient) => count + patient.output_documents.filter((output) => output.status === "DRAFT").length, 0);

  useEffect(() => {
    if (!token || !selectedId) return;
    apiFetch<BillingComparison[]>(`/patients/${selectedId}/billing/psych-eval-comparison`, token)
      .then(setComparison)
      .catch(() => setComparison([]));
    apiFetch<BillingSummary>(`/patients/${selectedId}/billing/latest`, token)
      .then(setBilling)
      .catch(() => setBilling(null));
  }, [token, selectedId]);

  async function createPatient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    const form = new FormData(event.currentTarget);
    await apiFetch<Patient>("/patients", token, {
      method: "POST",
      body: JSON.stringify({ name: form.get("name"), drive_folder_id: form.get("drive_folder_id") })
    });
    event.currentTarget.reset();
    await load();
  }

  async function generate(path: string, body: object) {
    if (!token || !selected) return;
    await apiFetch(path, token, { method: "POST", body: JSON.stringify(body) });
    const patient = await apiFetch<Patient>(`/patients/${selected.id}`, token);
    setPatients((items) => items.map((item) => (item.id === patient.id ? patient : item)));
    try {
      setBilling(await apiFetch<BillingSummary>(`/patients/${selected.id}/billing/latest`, token));
    } catch {
      setBilling(null);
    }
    setComparison(await apiFetch<BillingComparison[]>(`/patients/${selected.id}/billing/psych-eval-comparison`, token));
  }

  async function resyncDemoFiles() {
    if (!token || !selected) return;
    await apiFetch(`/patients/${selected.id}/sources/resync`, token, {
      method: "POST",
      body: JSON.stringify({
        files: [
          { id: `${selected.id}-intake`, name: "Headway Intake.pdf" },
          { id: `${selected.id}-phq9`, name: "PHQ-9 Assessment.pdf" },
          { id: `${selected.id}-zoom`, name: "042526-zoomnote.pdf" }
        ]
      })
    });
    const patient = await apiFetch<Patient>(`/patients/${selected.id}`, token);
    setPatients((items) => items.map((item) => (item.id === patient.id ? patient : item)));
  }

  async function updateClassification(source: SourceDocument, fileType: string) {
    if (!token) return;
    const patient = await apiFetch<Patient>(`/source-documents/${source.id}/classification`, token, {
      method: "PATCH",
      body: JSON.stringify({ file_type: fileType })
    });
    setPatients((items) => items.map((item) => (item.id === patient.id ? patient : item)));
  }

  const billingCodesOnly = billing ? `ICD-10 Codes: ${billing.icd10_codes}\nCPT Codes: ${billing.cpt_codes}` : "";

  return (
    <main className="min-h-screen text-ink">
      <AppHeader pendingReviewCount={pendingReviewCount} patientCount={patients.length} signedIn={Boolean(token)} />
      {!token ? <LoginPanel onToken={(value) => { setToken(value); load(value); }} /> : null}
      {error ? <div className="mx-auto mt-5 max-w-7xl rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 shadow-sm">{error}</div> : null}

      <section className="mx-auto grid max-w-7xl gap-6 p-5 lg:grid-cols-[340px_minmax(0,1fr)] xl:p-6">
        <PatientSidebar
          patients={filtered}
          selectedId={selectedId}
          query={query}
          onQuery={setQuery}
          onSelect={setSelectedId}
          onCreate={createPatient}
          disabled={!token}
        />

        <section className="min-w-0">
          {selected ? (
            <PatientWorkspace
              patient={selected}
              billing={billing}
              billingCodesOnly={billingCodesOnly}
              comparison={comparison}
              onGenerate={generate}
              onResync={resyncDemoFiles}
              onClassify={updateClassification}
            />
          ) : (
            <EmptyWorkspaceState />
          )}
        </section>
      </section>
    </main>
  );
}

function AppHeader({ pendingReviewCount, patientCount, signedIn }: { pendingReviewCount: number; patientCount: number; signedIn: boolean }) {
  return (
    <header className="border-b border-line/80 bg-cream/85 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-col gap-5 px-5 py-6 lg:flex-row lg:items-center lg:justify-between xl:px-6">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-moss text-white shadow-card">
            <Stethoscope size={23} />
          </div>
          <div>
            <h1 className="text-3xl font-bold tracking-normal text-ink">Clinical AI Webapp</h1>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">Drive intake, note generation, review, and Headway-ready billing.</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <HeaderChip icon={<FolderSync size={15} />} label="Drive sync ready" tone="green" />
          <HeaderChip icon={<NotebookPen size={15} />} label={`${pendingReviewCount} pending review`} tone={pendingReviewCount ? "amber" : "green"} />
          <HeaderChip icon={<ShieldCheck size={15} />} label={signedIn ? "Secure workspace" : "Sign-in required"} tone="neutral" />
          <HeaderChip icon={<Activity size={15} />} label={`${patientCount} patients`} tone="neutral" />
        </div>
      </div>
    </header>
  );
}

function HeaderChip({ icon, label, tone }: { icon: React.ReactNode; label: string; tone: "green" | "amber" | "neutral" }) {
  const toneClass = tone === "green" ? "border-moss/20 bg-sage text-moss" : tone === "amber" ? "border-amber/20 bg-amber/10 text-amber" : "border-line bg-white text-muted";
  return <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-semibold shadow-sm ${toneClass}`}>{icon}{label}</span>;
}

function PatientSidebar({
  patients,
  selectedId,
  query,
  onQuery,
  onSelect,
  onCreate,
  disabled
}: {
  patients: Patient[];
  selectedId: string | null;
  query: string;
  onQuery: (query: string) => void;
  onSelect: (id: string) => void;
  onCreate: (event: FormEvent<HTMLFormElement>) => void;
  disabled: boolean;
}) {
  return (
    <aside className="grid content-start gap-4">
      <NewPatientCard onCreate={onCreate} disabled={disabled} />
      <Card className="overflow-hidden p-0">
        <div className="border-b border-line p-4">
          <label className="flex items-center gap-2 rounded-xl border border-line bg-cream px-3 py-2.5 text-sm shadow-sm transition focus-within:border-moss/45 focus-within:ring-4 focus-within:ring-moss/10">
            <Search size={16} className="text-muted" />
            <input value={query} onChange={(event) => onQuery(event.target.value)} placeholder="Search patients" className="w-full bg-transparent text-ink outline-none placeholder:text-muted/60" />
          </label>
        </div>
        <div className="max-h-[560px] overflow-auto p-2">
          {patients.map((patient) => (
            <PatientListItem key={patient.id} patient={patient} active={patient.id === selectedId} onSelect={() => onSelect(patient.id)} />
          ))}
          {!patients.length ? <div className="p-5 text-center text-sm text-muted">No patients match this search.</div> : null}
        </div>
      </Card>
    </aside>
  );
}

function NewPatientCard({ onCreate, disabled }: { onCreate: (event: FormEvent<HTMLFormElement>) => void; disabled: boolean }) {
  return (
    <Card>
      <div className="mb-4 flex items-center gap-2">
        <div className="rounded-xl bg-sage p-2 text-moss"><FilePlus2 size={17} /></div>
        <div>
          <h2 className="text-base font-bold">New patient</h2>
          <p className="text-xs text-muted">Link a Drive folder to start intake processing.</p>
        </div>
      </div>
      <form onSubmit={onCreate} className="grid gap-3">
        <Field label="Patient name" name="name" placeholder="Jane Doe" disabled={disabled} />
        <Field label="Drive folder ID" name="drive_folder_id" placeholder="Google Drive folder ID" disabled={disabled} />
        <button disabled={disabled} className="focus-ring rounded-xl bg-moss px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-moss/90 disabled:cursor-not-allowed disabled:bg-muted/40">Create patient</button>
      </form>
    </Card>
  );
}

function PatientListItem({ patient, active, onSelect }: { patient: Patient; active: boolean; onSelect: () => void }) {
  const status = patientStatus(patient);
  return (
    <button onClick={onSelect} className={`mb-2 w-full rounded-2xl border p-4 text-left transition ${active ? "border-moss/35 bg-sage shadow-sm" : "border-transparent bg-white hover:border-line hover:bg-cream"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate font-semibold">{patient.name}</div>
          <div className="mt-1 truncate text-xs text-muted">Folder {patient.drive_folder_id}</div>
        </div>
        <StatusBadge value={status.value} />
      </div>
      <div className="mt-3 flex items-center gap-2 text-xs text-muted">
        <FileText size={13} />
        {patient.source_documents.length} sources · {patient.output_documents.length} outputs
      </div>
    </button>
  );
}

function EmptyWorkspaceState() {
  return (
    <Card className="min-h-[620px] content-center p-10 text-center">
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-sage text-moss shadow-sm">
        <Sparkles size={28} />
      </div>
      <h2 className="mt-6 text-2xl font-bold">Select a patient to begin</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-muted">Open a patient workspace to review Drive intake, generate documents, manage draft review, and prepare Headway billing.</p>
      <div className="mx-auto mt-7 grid max-w-2xl gap-3 text-left sm:grid-cols-2">
        {["Review intake", "Generate summary", "Create session note", "Prepare Headway billing"].map((item) => (
          <div key={item} className="flex items-center gap-3 rounded-2xl border border-line bg-cream p-4 text-sm font-semibold">
            <BadgeCheck size={16} className="text-moss" />
            {item}
          </div>
        ))}
      </div>
    </Card>
  );
}

function PatientWorkspace({
  patient,
  billing,
  billingCodesOnly,
  comparison,
  onGenerate,
  onResync,
  onClassify
}: {
  patient: Patient;
  billing: BillingSummary | null;
  billingCodesOnly: string;
  comparison: BillingComparison[];
  onGenerate: GenerateFn;
  onResync: () => Promise<void>;
  onClassify: (source: SourceDocument, fileType: string) => Promise<void>;
}) {
  return (
    <div className="grid gap-5">
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <PatientOverviewCard patient={patient} />
        <QuickActionsCard patient={patient} billing={billing} onGenerate={onGenerate} onResync={onResync} />
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <SourceDocumentsCard patient={patient} onClassify={onClassify} />
        <WorkflowStatusCard patient={patient} billing={billing} />
      </div>
      <BillingSummaryCard billing={billing} billingCodesOnly={billingCodesOnly} />
      <ReimbursementComparisonCard rows={comparison} />
    </div>
  );
}

function PatientOverviewCard({ patient }: { patient: Patient }) {
  const latestIntake = latestSource(patient, "INTAKE");
  const latestZoom = latestSource(patient, "ZOOM_NOTE");
  const summary = latestOutput(patient, "SUMMARY");
  const plan = latestOutput(patient, "TREATMENT_PLAN");
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-moss">
            <LockKeyhole size={14} />
            Active patient workspace
          </div>
          <h2 className="text-2xl font-bold">{patient.name}</h2>
          <p className="mt-1 text-sm text-muted">Drive folder {patient.drive_folder_id}</p>
        </div>
        <StatusBadge value={patientStatus(patient).value} />
      </div>
      <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Latest intake" value={latestIntake ? formatDate(latestIntake.uploaded_at) : "Not received"} />
        <Metric label="Latest note" value={latestZoom ? formatDate(latestZoom.uploaded_at) : "Not received"} />
        <Metric label="Summary" value={summary?.status || "Not generated"} />
        <Metric label="Treatment plan" value={plan?.status || "Not ready"} />
      </div>
    </Card>
  );
}

function QuickActionsCard({ patient, billing, onGenerate, onResync }: { patient: Patient; billing: BillingSummary | null; onGenerate: GenerateFn; onResync: () => Promise<void> }) {
  const zoom = patient.source_documents.find((doc) => doc.file_type === "ZOOM_NOTE");
  return (
    <Card>
      <SectionHeader title="Quick actions" subtitle="Generate drafts and keep Drive sources current." />
      <div className="mt-4 grid gap-3">
        <ActionButton tone="primary" onClick={() => onGenerate(`/patients/${patient.id}/generate/summary`, { save_pdf: false })}>Generate Summary</ActionButton>
        <ActionButton tone="primary" disabled={!zoom} onClick={() => zoom && onGenerate(`/patients/${patient.id}/generate/session-note`, { source_document_id: zoom.id, save_pdf: false })}>Generate Session Note</ActionButton>
        <ActionButton tone="secondary" onClick={() => onGenerate(`/patients/${patient.id}/generate/treatment-plan`, { save_pdf: false })}>Generate Treatment Plan</ActionButton>
        <ActionButton tone="secondary" onClick={onResync} icon={<RefreshCw size={16} />}>Resync sample files</ActionButton>
        <ActionButton tone="accent" disabled={!billing} onClick={() => billing && navigator.clipboard.writeText(billing.headway_block)} icon={<Clipboard size={16} />}>Copy Billing Summary</ActionButton>
      </div>
    </Card>
  );
}

function SourceDocumentsCard({ patient, onClassify }: { patient: Patient; onClassify: (source: SourceDocument, fileType: string) => Promise<void> }) {
  return (
    <Card>
      <SectionHeader title="Source documents" subtitle="Classify source files before generation." />
      <div className="mt-4 grid gap-3">
        {patient.source_documents.map((source) => (
          <div key={source.id} className="grid gap-3 rounded-2xl border border-line bg-cream p-4 sm:grid-cols-[minmax(0,1fr)_160px] sm:items-center">
            <div className="min-w-0">
              <div className="truncate font-semibold">{source.name}</div>
              <div className="mt-1 text-xs text-muted">{formatDate(source.uploaded_at)} · {source.processed ? "processed" : "awaiting workflow"}</div>
            </div>
            <select className="focus-ring rounded-xl border border-line bg-white px-3 py-2 text-sm font-semibold text-ink" value={source.file_type} onChange={(event) => onClassify(source, event.target.value)}>
              <option>INTAKE</option>
              <option>ASSESSMENT</option>
              <option>ZOOM_NOTE</option>
              <option>UNKNOWN</option>
            </select>
          </div>
        ))}
        {!patient.source_documents.length ? <Empty text="No source documents synced yet." /> : null}
      </div>
    </Card>
  );
}

function WorkflowStatusCard({ patient, billing }: { patient: Patient; billing: BillingSummary | null }) {
  const rows = [
    ["Intake received", Boolean(latestSource(patient, "INTAKE"))],
    ["Assessments received", patient.source_documents.some((doc) => doc.file_type === "ASSESSMENT")],
    ["Summary generated", Boolean(latestOutput(patient, "SUMMARY"))],
    ["Summary reviewed", latestOutput(patient, "SUMMARY")?.status === "FINAL"],
    ["Zoom note received", Boolean(latestSource(patient, "ZOOM_NOTE"))],
    ["Session note generated", Boolean(latestOutput(patient, "SESSION_NOTE"))],
    ["Treatment plan ready", Boolean(latestOutput(patient, "TREATMENT_PLAN"))],
    ["Billing ready", Boolean(billing)]
  ] as const;
  return (
    <Card>
      <SectionHeader title="Workflow status" subtitle="Progress from Drive intake to billing readiness." />
      <div className="mt-4 grid gap-2">
        {rows.map(([label, done]) => (
          <div key={label} className="flex items-center justify-between rounded-2xl border border-line bg-white px-4 py-3">
            <span className="text-sm font-semibold">{label}</span>
            <StatusBadge value={done ? "READY" : "PENDING"} />
          </div>
        ))}
      </div>
    </Card>
  );
}

function BillingSummaryCard({ billing, billingCodesOnly }: { billing: BillingSummary | null; billingCodesOnly: string }) {
  return (
    <Card className="border-moss/20 bg-gradient-to-br from-white to-sage/70">
      <SectionHeader title="Billing summary" subtitle="Headway-ready fields for clinical operations." />
      {billing ? (
        <div className="mt-4 grid gap-4">
          <div className="grid gap-3 rounded-2xl border border-moss/15 bg-white p-4 sm:grid-cols-2 lg:grid-cols-3">
            {parseBillingBlock(billing.headway_block).map(([label, value]) => <Metric key={label} label={label} value={value || "Needs confirmation"} />)}
          </div>
          <pre className="whitespace-pre-wrap rounded-2xl border border-line bg-cream p-4 text-sm leading-6 text-ink">{billing.headway_block}</pre>
          <div className="flex flex-wrap gap-2">
            <CopyButton text={billing.headway_block} label="Copy Billing Summary" />
            <CopyButton text={billingCodesOnly} label="Copy ICD/CPT Only" />
            <CopyButton text={`${billing.headway_block}\n\n${JSON.stringify(billing.reimbursement_notes, null, 2)}`} label="Copy All Fields" />
          </div>
        </div>
      ) : (
        <Empty text="Billing requires confirmed service, diagnosis, minutes, CPT support, and reimbursement rates." />
      )}
    </Card>
  );
}

function ReimbursementComparisonCard({ rows }: { rows: BillingComparison[] }) {
  const bestRows = rows.filter((row) => row.recommendation === "Option B");
  return (
    <Card>
      <SectionHeader title="Psychiatric evaluation comparison" subtitle="Compare 90792 against E/M plus psychotherapy add-on." />
      <div className="mt-4 overflow-auto">
        <table className="w-full min-w-[820px] border-separate border-spacing-0 text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-muted">
              <th className="border-b border-line pb-3">Payer</th>
              <th className="border-b border-line pb-3">90792</th>
              <th className="border-b border-line pb-3">E/M + add-on</th>
              <th className="border-b border-line pb-3">Difference</th>
              <th className="border-b border-line pb-3">Recommendation</th>
              <th className="border-b border-line pb-3">Reason</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.payer} className={row.recommendation === "Option B" ? "bg-sage/40" : ""}>
                <td className="border-b border-line py-3 pr-4 font-semibold">{row.payer}</td>
                <td className="border-b border-line py-3 pr-4">{formatMoney(row.option_a_total)}</td>
                <td className="border-b border-line py-3 pr-4">{formatMoney(row.option_b_total)}</td>
                <td className="border-b border-line py-3 pr-4">{formatMoney(row.difference)}</td>
                <td className="border-b border-line py-3 pr-4"><StatusBadge value={row.recommendation === "Option B" ? "READY" : "PENDING"} /></td>
                <td className="border-b border-line py-3 text-muted">{row.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length ? <Empty text="Select a patient to load reimbursement comparison." /> : null}
      </div>
      {bestRows.length ? <p className="mt-3 text-xs font-semibold text-moss">{bestRows.length} payer rows currently favor E/M plus psychotherapy add-on.</p> : null}
    </Card>
  );
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`rounded-3xl border border-line bg-white p-5 shadow-card ${className}`}>{children}</section>;
}

function SectionHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div>
      <h2 className="text-lg font-bold">{title}</h2>
      <p className="mt-1 text-sm leading-5 text-muted">{subtitle}</p>
    </div>
  );
}

function Field({ label, name, placeholder, disabled }: { label: string; name: string; placeholder: string; disabled: boolean }) {
  return (
    <label className="grid gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
      {label}
      <input name={name} required disabled={disabled} placeholder={placeholder} className="focus-ring rounded-xl border border-line bg-cream px-3 py-2.5 text-sm normal-case tracking-normal text-ink placeholder:text-muted/50 disabled:opacity-60" />
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-line bg-cream px-4 py-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-1 truncate text-sm font-bold text-ink">{value}</div>
    </div>
  );
}

function ActionButton({ children, onClick, disabled, tone, icon }: { children: React.ReactNode; onClick: () => void; disabled?: boolean; tone: "primary" | "secondary" | "accent"; icon?: React.ReactNode }) {
  const toneClass = tone === "primary" ? "bg-moss text-white hover:bg-moss/90" : tone === "accent" ? "border-clay/25 bg-clay/10 text-clay hover:bg-clay/15" : "border-line bg-white text-ink hover:bg-cream";
  return (
    <button disabled={disabled} onClick={onClick} className={`focus-ring inline-flex items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-semibold shadow-sm transition disabled:cursor-not-allowed disabled:opacity-45 ${toneClass}`}>
      {icon}
      {children}
    </button>
  );
}

function CopyButton({ text, label }: { text: string; label: string }) {
  return (
    <button onClick={() => navigator.clipboard.writeText(text)} className="focus-ring inline-flex items-center gap-2 rounded-xl border border-line bg-white px-4 py-2.5 text-sm font-semibold shadow-sm transition hover:bg-cream">
      <Clipboard size={16} />
      {label}
    </button>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-2xl border border-dashed border-line bg-cream/70 p-6 text-center text-sm leading-6 text-muted">{text}</div>;
}

function patientStatus(patient: Patient) {
  if (patient.output_documents.some((output) => output.doc_type === "TREATMENT_PLAN" && output.status === "FINAL")) return { label: "Finalized", value: "READY" };
  if (patient.output_documents.some((output) => output.status === "DRAFT")) return { label: "Needs review", value: "REVIEW" };
  if (patient.output_documents.some((output) => output.doc_type === "SUMMARY")) return { label: "Summary ready", value: "READY" };
  if (patient.source_documents.some((source) => source.file_type === "INTAKE")) return { label: "New intake", value: "PENDING" };
  return { label: "Inactive", value: "INACTIVE" };
}

function latestSource(patient: Patient, type: string) {
  return patient.source_documents.filter((source) => source.file_type === type).sort((a, b) => Date.parse(b.uploaded_at) - Date.parse(a.uploaded_at))[0];
}

function latestOutput(patient: Patient, type: string) {
  return patient.output_documents.filter((output) => output.doc_type === type).sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0];
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

function formatMoney(value: number | null) {
  if (value === null) return "Needs rates";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function parseBillingBlock(block: string) {
  return block.split("\n").map((line) => {
    const [label, ...rest] = line.split(":");
    return [label, rest.join(":").trim()] as const;
  });
}
