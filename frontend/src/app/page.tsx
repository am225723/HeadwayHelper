"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Activity,
  BadgeCheck,
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  Clipboard,
  Clock3,
  CreditCard,
  Eye,
  FileCheck2,
  FilePlus2,
  FileText,
  FolderSync,
  Layers3,
  LockKeyhole,
  MoreHorizontal,
  NotebookPen,
  RefreshCw,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  UserRound,
  WalletCards
} from "lucide-react";
import { LoginPanel } from "@/components/login-panel";
import { StatusBadge } from "@/components/status-badge";
import { AdminConfig, API_BASE, BillingComparison, BillingSummary, CurrentUser, Patient, SourceDocument, TemplatePreview, apiFetch } from "@/lib/api";
import { copyToClipboard } from "@/lib/clipboard";

type GenerateFn = (path: string, body: object) => Promise<void>;

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [comparison, setComparison] = useState<BillingComparison[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [adminConfig, setAdminConfig] = useState<AdminConfig | null>(null);

  useEffect(() => {
    setToken(localStorage.getItem("clinical-ai-token"));
  }, []);

  async function load(nextToken = token) {
    if (!nextToken) return;
    setError(null);
    try {
      const data = await apiFetch<{ items: Patient[] }>("/patients", nextToken);
      const user = await apiFetch<CurrentUser>("/me", nextToken);
      setPatients(data.items);
      setCurrentUser(user);
      if (user.role === "ADMIN") setAdminConfig(await loadAdminConfig(nextToken));
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
      <WorkspaceStatusBar signedIn={Boolean(token)} patientCount={patients.length} pendingReviewCount={pendingReviewCount} />
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
          {currentUser?.role === "ADMIN" && adminConfig && token ? <AdminSettingsPanel config={adminConfig} token={token} onConfig={setAdminConfig} /> : null}
        </section>
      </section>
    </main>
  );
}

async function loadAdminConfig(token: string): Promise<AdminConfig> {
  const [rates, billingRules, serviceTypes, classificationRules, settings, templates] = await Promise.all([
    apiFetch<AdminConfig["rates"]>("/admin/reimbursement-rates", token),
    apiFetch<AdminConfig["billingRules"]>("/admin/billing-rules", token),
    apiFetch<AdminConfig["serviceTypes"]>("/admin/service-types", token),
    apiFetch<AdminConfig["classificationRules"]>("/admin/classification-rules", token),
    apiFetch<AdminConfig["settings"]>("/admin/settings", token),
    apiFetch<AdminConfig["templates"]>("/admin/templates", token)
  ]);
  return { rates, billingRules, serviceTypes, classificationRules, settings, templates };
}

function AppHeader({ pendingReviewCount, patientCount, signedIn }: { pendingReviewCount: number; patientCount: number; signedIn: boolean }) {
  return (
    <header className="relative overflow-hidden border-b border-line/80 bg-cream/90 backdrop-blur">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_15%_20%,rgba(49,95,76,0.12),transparent_28rem),radial-gradient(circle_at_90%_0%,rgba(201,111,85,0.10),transparent_22rem)]" />
      <div className="relative mx-auto flex max-w-7xl flex-col gap-5 px-5 py-7 lg:flex-row lg:items-center lg:justify-between xl:px-6">
        <div className="flex items-start gap-4">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-3xl bg-moss text-white shadow-card ring-8 ring-moss/10">
            <Stethoscope size={23} />
          </div>
          <div>
            <div className="mb-1 inline-flex items-center gap-2 rounded-full border border-moss/15 bg-white/70 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.16em] text-moss shadow-sm">
              <ShieldCheck size={13} />
              Therapy operations command center
            </div>
            <h1 className="font-serif text-3xl font-semibold tracking-tight text-ink sm:text-4xl">Clinical AI Webapp</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">Drive intake, note generation, review, and Headway-ready billing for a calm, audit-ready clinical workflow.</p>
          </div>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:max-w-md">
          <HeaderChip icon={<FolderSync size={15} />} label="Drive sync ready" tone="green" />
          <HeaderChip icon={<NotebookPen size={15} />} label={`${pendingReviewCount} pending review`} tone={pendingReviewCount ? "amber" : "green"} />
          <HeaderChip icon={<ShieldCheck size={15} />} label={signedIn ? "Secure workspace" : "Sign-in required"} tone="neutral" />
          <HeaderChip icon={<UserRound size={15} />} label={signedIn ? "Clinical admin" : `${patientCount} patients`} tone="neutral" />
        </div>
      </div>
    </header>
  );
}

function HeaderChip({ icon, label, tone }: { icon: React.ReactNode; label: string; tone: "green" | "amber" | "neutral" }) {
  const toneClass = tone === "green" ? "border-moss/20 bg-sage text-moss" : tone === "amber" ? "border-amber/20 bg-amber/10 text-amber" : "border-line bg-white/85 text-muted";
  return <span className={`inline-flex items-center gap-2 rounded-2xl border px-3.5 py-2.5 text-xs font-semibold shadow-sm backdrop-blur ${toneClass}`}>{icon}{label}</span>;
}

function WorkspaceStatusBar({ signedIn, patientCount, pendingReviewCount }: { signedIn: boolean; patientCount: number; pendingReviewCount: number }) {
  return (
    <div className="border-b border-line/70 bg-white/55">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-5 py-3 text-xs font-semibold text-muted xl:px-6">
        <span className="inline-flex items-center gap-2"><Activity size={14} className="text-moss" /> Operational status normal</span>
        <span className="hidden h-1 w-1 rounded-full bg-line sm:block" />
        <span>{patientCount} active records in workspace</span>
        <span className="hidden h-1 w-1 rounded-full bg-line sm:block" />
        <span>{pendingReviewCount ? `${pendingReviewCount} drafts awaiting review` : "No drafts awaiting review"}</span>
        <span className="ml-auto inline-flex items-center gap-2 rounded-full border border-line bg-white px-3 py-1.5 text-ink shadow-sm">
          <LockKeyhole size={13} className="text-moss" />
          {signedIn ? "Session protected" : "Authentication required"}
        </span>
      </div>
    </div>
  );
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
    <Card className="bg-gradient-to-br from-white to-sage/45">
      <div className="mb-4 flex items-center gap-2">
        <div className="rounded-2xl bg-white p-2 text-moss shadow-sm"><FilePlus2 size={17} /></div>
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
    <button onClick={onSelect} className={`group mb-2 w-full rounded-2xl border p-3.5 text-left transition duration-200 ${active ? "border-moss/35 bg-sage shadow-sm ring-4 ring-moss/5" : "border-transparent bg-white hover:-translate-y-0.5 hover:border-line hover:bg-cream hover:shadow-sm"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <Initials name={patient.name} small />
          <div className="min-w-0">
            <div className="truncate font-semibold">{patient.name}</div>
            <div className="mt-1 truncate text-xs text-muted">{shortMrn(patient)} · folder {patient.drive_folder_id.slice(0, 8)}</div>
          </div>
        </div>
        <StatusBadge value={status.value} />
      </div>
      <div className="mt-3 flex items-center gap-2 pl-11 text-xs text-muted">
        <FileText size={13} />
        {recentActivity(patient)}
        <ChevronRight size={13} className="ml-auto opacity-0 transition group-hover:opacity-100" />
      </div>
    </button>
  );
}

function EmptyWorkspaceState() {
  return (
    <Card className="min-h-[620px] content-center overflow-hidden bg-gradient-to-br from-white via-white to-sage/70 p-10 text-center">
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-white text-moss shadow-card ring-8 ring-moss/10">
        <Sparkles size={28} />
      </div>
      <h2 className="mt-6 font-serif text-3xl font-semibold">Select a patient to begin</h2>
      <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-muted">Open a patient cockpit to review Drive intake, generate clinical documents, manage approvals, and prepare Headway billing with less context switching.</p>
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
    <Card className="overflow-hidden bg-gradient-to-br from-white via-white to-sage/55">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-4">
          <Initials name={patient.name} />
          <div className="min-w-0">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-moss">
            <LockKeyhole size={14} />
            Active patient workspace
          </div>
          <h2 className="truncate font-serif text-3xl font-semibold">{patient.name}</h2>
          <p className="mt-1 text-sm text-muted">{shortMrn(patient)} · Age not recorded · Pronouns not recorded</p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-muted">
            <span className="rounded-full border border-line bg-white px-3 py-1.5">Clinician: Dr. Zelisko</span>
            <span className="rounded-full border border-line bg-white px-3 py-1.5">Next appointment: Not scheduled</span>
          </div>
          </div>
        </div>
        <StatusBadge value={patientStatus(patient).value} />
      </div>
      <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric icon={<FileText size={15} />} label="Latest intake" value={latestIntake ? formatDate(latestIntake.uploaded_at) : "Not received"} />
        <Metric icon={<CalendarClock size={15} />} label="Latest note" value={latestZoom ? formatDate(latestZoom.uploaded_at) : "Not received"} />
        <Metric icon={<FileCheck2 size={15} />} label="Summary" value={summary?.status || "Not generated"} />
        <Metric icon={<Layers3 size={15} />} label="Treatment plan" value={plan?.status || "Not ready"} />
      </div>
    </Card>
  );
}

function QuickActionsCard({ patient, billing, onGenerate, onResync }: { patient: Patient; billing: BillingSummary | null; onGenerate: GenerateFn; onResync: () => Promise<void> }) {
  const zoom = patient.source_documents.find((doc) => doc.file_type === "ZOOM_NOTE");
  return (
    <Card>
      <SectionHeader eyebrow="Clinical automation" title="Quick actions" subtitle="Generate drafts, review outputs, and prepare billing without leaving the patient cockpit." />
      <div className="mt-4 grid gap-3">
        <ActionButton tone="primary" icon={<Sparkles size={16} />} subtext="Intake + assessments" onClick={() => onGenerate(`/patients/${patient.id}/generate/summary`, { save_pdf: false })}>Generate intake summary</ActionButton>
        <ActionButton tone="primary" icon={<NotebookPen size={16} />} subtext={zoom ? "From selected Zoom note" : "Needs Zoom note"} disabled={!zoom} onClick={() => zoom && onGenerate(`/patients/${patient.id}/generate/session-note`, { source_document_id: zoom.id, save_pdf: false })}>Draft session note</ActionButton>
        <ActionButton tone="secondary" icon={<Layers3 size={16} />} subtext="Summary + latest note" onClick={() => onGenerate(`/patients/${patient.id}/generate/treatment-plan`, { save_pdf: false })}>Generate treatment plan</ActionButton>
        <ActionButton tone="secondary" onClick={onResync} icon={<RefreshCw size={16} />} subtext="Pull Drive changes">Resync files</ActionButton>
        <ActionButton tone="accent" disabled={!billing} onClick={() => billing && copyToClipboard(billing.headway_block)} icon={<Clipboard size={16} />} subtext="Headway-ready block">Copy billing summary</ActionButton>
      </div>
    </Card>
  );
}

function SourceDocumentsCard({ patient, onClassify }: { patient: Patient; onClassify: (source: SourceDocument, fileType: string) => Promise<void> }) {
  return (
    <Card>
      <SectionHeader eyebrow="Drive library" title="Source documents" subtitle="Review file types, status, and workflow readiness." />
      <div className="mt-4 grid gap-3">
        {patient.source_documents.map((source) => (
          <div key={source.id} className="group grid gap-3 rounded-2xl border border-line bg-cream p-4 transition hover:-translate-y-0.5 hover:bg-white hover:shadow-sm sm:grid-cols-[minmax(0,1fr)_160px_36px] sm:items-center">
            <div className="flex min-w-0 items-start gap-3">
              <div className="rounded-2xl bg-white p-2 text-moss shadow-sm"><FileText size={16} /></div>
              <div className="min-w-0">
                <div className="truncate font-semibold">{documentLabel(source)}</div>
                <div className="mt-1 truncate text-xs text-muted">{source.name}</div>
                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                  <span className="rounded-full border border-line bg-white px-2.5 py-1 text-muted">{formatDate(source.uploaded_at)}</span>
                  <span className={`rounded-full border px-2.5 py-1 ${source.processed ? "border-moss/20 bg-sage text-moss" : "border-amber/20 bg-amber/10 text-amber"}`}>{source.processed ? "Ready" : "Awaiting workflow"}</span>
                </div>
              </div>
            </div>
            <select className="focus-ring rounded-xl border border-line bg-white px-3 py-2 text-sm font-semibold text-ink" value={source.file_type} onChange={(event) => onClassify(source, event.target.value)}>
              <option>INTAKE</option>
              <option>ASSESSMENT</option>
              <option>ZOOM_NOTE</option>
              <option>UNKNOWN</option>
            </select>
            <button className="hidden h-9 w-9 items-center justify-center rounded-xl border border-line bg-white text-muted transition hover:text-ink sm:flex" type="button" aria-label="More document actions"><MoreHorizontal size={16} /></button>
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
      <SectionHeader eyebrow="Care pathway" title="Workflow timeline" subtitle="Track clinical documentation from intake to billing." />
      <div className="mt-5 grid gap-0">
        {rows.map(([label, done], index) => (
          <div key={label} className="relative grid grid-cols-[34px_minmax(0,1fr)_auto] gap-3 pb-4 last:pb-0">
            {index < rows.length - 1 ? <span className="absolute left-[15px] top-8 h-[calc(100%-1.4rem)] w-px bg-line" /> : null}
            <span className={`z-10 flex h-8 w-8 items-center justify-center rounded-full border shadow-sm ${done ? "border-moss bg-moss text-white" : "border-line bg-white text-muted"}`}>
              {done ? <CheckCircle2 size={15} /> : <Clock3 size={15} />}
            </span>
            <div>
              <div className="text-sm font-semibold">{label}</div>
              <div className="mt-1 text-xs text-muted">{done ? "Complete and available in workspace" : "Waiting for source or review"}</div>
            </div>
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
      <SectionHeader eyebrow="Revenue readiness" title="Billing command center" subtitle="Review coding fields, claim readiness, and Headway copy actions." />
      {billing ? (
        <div className="mt-4 grid gap-4">
          <div className="grid gap-3 md:grid-cols-4">
            <Metric icon={<CreditCard size={15} />} label="Selected CPT" value={billing.cpt_codes || "Needs code"} />
            <Metric icon={<WalletCards size={15} />} label="Payer" value="Needs confirmation" />
            <Metric icon={<CircleDollarSign size={15} />} label="Patient responsibility" value="Not calculated" />
            <Metric icon={<BadgeCheck size={15} />} label="Status" value="Billing ready" />
          </div>
          <div className="grid gap-3 rounded-2xl border border-moss/15 bg-white p-4 sm:grid-cols-2 lg:grid-cols-3">
            {parseBillingBlock(billing.headway_block).map(([label, value]) => <Metric key={label} label={label} value={value || "Needs confirmation"} />)}
          </div>
          <pre className="whitespace-pre-wrap rounded-2xl border border-line bg-cream p-4 text-sm leading-6 text-ink">{billing.headway_block}</pre>
          <div className="flex flex-wrap gap-2">
            <CopyButton text={billing.headway_block} label="Copy Billing Summary" />
            <CopyButton text={billingCodesOnly} label="Copy ICD/CPT Only" />
            <CopyButton text={`${billing.headway_block}\n\n${JSON.stringify(billing.reimbursement_notes, null, 2)}`} label="Copy All Fields" />
            <UtilityButton label="Preview claim" icon={<Eye size={16} />} />
            <UtilityButton label="Send to Headway" icon={<Send size={16} />} disabled />
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
      <SectionHeader eyebrow="Reimbursement analytics" title="Psychiatric evaluation comparison" subtitle="Compare 90792 against E/M plus psychotherapy add-on." />
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <OptionCard label="Option A" title="90792" value={formatMoney(rows[0]?.option_a_total ?? null)} recommended={rows.some((row) => row.recommendation === "Option A")} />
        <OptionCard label="Option B" title="E/M + psychotherapy add-on" value={formatMoney(rows[0]?.option_b_total ?? null)} recommended={rows.some((row) => row.recommendation === "Option B")} />
      </div>
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

function AdminSettingsPanel({ config, token, onConfig }: { config: AdminConfig; token: string; onConfig: (config: AdminConfig) => void }) {
  const activeRates = config.rates.filter((rate) => rate.is_active);
  const inactiveRates = config.rates.length - activeRates.length;
  const [message, setMessage] = useState<string | null>(null);

  async function refresh(nextMessage?: string) {
    onConfig(await loadAdminConfig(token));
    setMessage(nextMessage || null);
  }

  async function saveRate(event: FormEvent<HTMLFormElement>, rateId: string) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await apiFetch(`/admin/reimbursement-rates/${rateId}`, token, {
      method: "PUT",
      body: JSON.stringify({
        payer_name: form.get("payer_name"),
        cpt_code: form.get("cpt_code"),
        amount: Number(form.get("amount") || 0),
        is_active: form.get("is_active") === "on",
        notes: form.get("notes") || null
      })
    });
    await refresh("Rate saved.");
  }

  async function createRate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await apiFetch("/admin/reimbursement-rates", token, {
      method: "POST",
      body: JSON.stringify({
        payer_name: form.get("payer_name"),
        cpt_code: form.get("cpt_code"),
        amount: Number(form.get("amount") || 0),
        is_active: true,
        notes: form.get("notes") || null
      })
    });
    event.currentTarget.reset();
    await refresh("Rate added.");
  }

  async function saveServiceType(event: FormEvent<HTMLFormElement>, serviceTypeId: string) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await apiFetch(`/admin/service-types/${serviceTypeId}`, token, {
      method: "PUT",
      body: JSON.stringify({
        name: form.get("name"),
        display_order: Number(form.get("display_order") || 0),
        is_active: form.get("is_active") === "on"
      })
    });
    await refresh("Service type saved.");
  }

  async function createServiceType(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await apiFetch("/admin/service-types", token, {
      method: "POST",
      body: JSON.stringify({
        name: form.get("name"),
        display_order: Number(form.get("display_order") || 0),
        is_active: true
      })
    });
    event.currentTarget.reset();
    await refresh("Service type added.");
  }

  async function saveClassificationRule(event: FormEvent<HTMLFormElement>, ruleId: string) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await apiFetch(`/admin/classification-rules/${ruleId}`, token, {
      method: "PUT",
      body: JSON.stringify({
        category: form.get("category"),
        keyword_or_pattern: form.get("keyword_or_pattern"),
        is_active: form.get("is_active") === "on"
      })
    });
    await refresh("Classification rule saved.");
  }

  async function createClassificationRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await apiFetch("/admin/classification-rules", token, {
      method: "POST",
      body: JSON.stringify({
        category: form.get("category"),
        keyword_or_pattern: form.get("keyword_or_pattern"),
        is_active: true
      })
    });
    event.currentTarget.reset();
    await refresh("Classification rule added.");
  }

  return (
    <div className="mt-5 grid gap-5">
      <Card className="border-moss/20 bg-gradient-to-br from-white to-sage/60">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <SectionHeader eyebrow="Admin controls" title="Backend-owned configuration" subtitle="Rates, coding rules, service types, classification, workflow settings, and templates are loaded from backend admin APIs." />
          <span className="inline-flex items-center gap-2 rounded-full border border-moss/20 bg-white px-3 py-2 text-xs font-bold text-moss shadow-sm">
            <Settings2 size={14} />
            Admin only
          </span>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="Rate rows" value={`${config.rates.length} total`} />
          <Metric label="Active rates" value={`${activeRates.length} active`} />
          <Metric label="Inactive placeholders" value={`${inactiveRates} need rates`} />
          <Metric label="Templates" value={`${config.templates.length} registered`} />
        </div>
        {message ? <div className="mt-4 rounded-2xl border border-moss/20 bg-white px-4 py-3 text-sm font-semibold text-moss shadow-sm">{message}</div> : null}
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <AdminRatesEditor rates={config.rates} onCreate={createRate} onSave={saveRate} />
        <AdminServiceTypesEditor serviceTypes={config.serviceTypes} onCreate={createServiceType} onSave={saveServiceType} />
        <AdminClassificationEditor rules={config.classificationRules} onCreate={createClassificationRule} onSave={saveClassificationRule} />
        <AdminMiniTable
          title="Billing rules"
          subtitle="CPT allowlists, modifier logic, and thresholds."
          rows={config.billingRules.map((rule) => [rule.rule_key, JSON.stringify(rule.rule_value_json).slice(0, 64), rule.description || ""])}
        />
        <AdminMiniTable
          title="Template registry"
          subtitle="Production HTML templates and placeholder metadata."
          rows={config.templates.map((template) => [template.document_type, `${template.template_name} v${template.version}`, `${template.placeholders.length} placeholders`])}
        />
        <AdminTemplatePreview templates={config.templates} token={token} />
        <AdminMiniTable
          title="Workflow settings"
          subtitle="Autosave, review, Drive scan, and default payer settings."
          rows={config.settings.map((setting) => [setting.setting_key, JSON.stringify(setting.setting_value_json).slice(0, 64), setting.description || ""])}
        />
      </div>
    </div>
  );
}

function AdminRatesEditor({ rates, onCreate, onSave }: { rates: AdminConfig["rates"]; onCreate: (event: FormEvent<HTMLFormElement>) => Promise<void>; onSave: (event: FormEvent<HTMLFormElement>, rateId: string) => Promise<void> }) {
  return (
    <Card>
      <SectionHeader title="Reimbursement rates" subtitle="Edit backend payer/CPT values used by billing recommendations." />
      <form onSubmit={onCreate} className="mt-4 grid gap-2 rounded-2xl border border-line bg-cream p-3 sm:grid-cols-[1fr_120px_100px_auto]">
        <input name="payer_name" required placeholder="Payer name" className="admin-input" />
        <input name="cpt_code" required placeholder="CPT" className="admin-input" />
        <input name="amount" required type="number" min="0" step="0.01" placeholder="Amount" className="admin-input" />
        <button className="rounded-xl bg-moss px-3 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-moss/90">Add rate</button>
      </form>
      <div className="mt-4 grid max-h-[430px] gap-2 overflow-auto pr-1">
        {rates.slice(0, 18).map((rate) => (
          <form key={rate.id} onSubmit={(event) => onSave(event, rate.id)} className="grid gap-2 rounded-2xl border border-line bg-white p-3 text-xs shadow-sm sm:grid-cols-[1fr_84px_96px_86px_auto] sm:items-center">
            <input name="payer_name" defaultValue={rate.payer_name} className="admin-input font-semibold" />
            <input name="cpt_code" defaultValue={rate.cpt_code} className="admin-input" />
            <input name="amount" type="number" min="0" step="0.01" defaultValue={rate.amount} className="admin-input" />
            <label className="flex items-center gap-2 font-semibold text-muted">
              <input name="is_active" type="checkbox" defaultChecked={rate.is_active} className="h-4 w-4 accent-moss" />
              Active
            </label>
            <input name="notes" defaultValue={rate.notes || ""} placeholder="Notes" className="admin-input sm:hidden" />
            <button className="rounded-xl border border-line bg-cream px-3 py-2 font-bold text-moss transition hover:bg-sage">Save</button>
          </form>
        ))}
      </div>
    </Card>
  );
}

function AdminServiceTypesEditor({ serviceTypes, onCreate, onSave }: { serviceTypes: AdminConfig["serviceTypes"]; onCreate: (event: FormEvent<HTMLFormElement>) => Promise<void>; onSave: (event: FormEvent<HTMLFormElement>, serviceTypeId: string) => Promise<void> }) {
  return (
    <Card>
      <SectionHeader title="Service types" subtitle="Backend service labels available for billing and generation flows." />
      <form onSubmit={onCreate} className="mt-4 grid gap-2 rounded-2xl border border-line bg-cream p-3 sm:grid-cols-[1fr_90px_auto]">
        <input name="name" required placeholder="Service name" className="admin-input" />
        <input name="display_order" type="number" defaultValue={serviceTypes.length} className="admin-input" />
        <button className="rounded-xl bg-moss px-3 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-moss/90">Add service</button>
      </form>
      <div className="mt-4 grid gap-2">
        {serviceTypes.map((serviceType) => (
          <form key={serviceType.id} onSubmit={(event) => onSave(event, serviceType.id)} className="grid gap-2 rounded-2xl border border-line bg-white p-3 text-xs shadow-sm sm:grid-cols-[1fr_90px_86px_auto] sm:items-center">
            <input name="name" defaultValue={serviceType.name} className="admin-input font-semibold" />
            <input name="display_order" type="number" defaultValue={serviceType.display_order} className="admin-input" />
            <label className="flex items-center gap-2 font-semibold text-muted">
              <input name="is_active" type="checkbox" defaultChecked={serviceType.is_active} className="h-4 w-4 accent-moss" />
              Active
            </label>
            <button className="rounded-xl border border-line bg-cream px-3 py-2 font-bold text-moss transition hover:bg-sage">Save</button>
          </form>
        ))}
      </div>
    </Card>
  );
}

function AdminClassificationEditor({ rules, onCreate, onSave }: { rules: AdminConfig["classificationRules"]; onCreate: (event: FormEvent<HTMLFormElement>) => Promise<void>; onSave: (event: FormEvent<HTMLFormElement>, ruleId: string) => Promise<void> }) {
  return (
    <Card>
      <SectionHeader title="Classification rules" subtitle="Keywords and regex patterns used by Drive file sync." />
      <form onSubmit={onCreate} className="mt-4 grid gap-2 rounded-2xl border border-line bg-cream p-3 sm:grid-cols-[130px_1fr_auto]">
        <select name="category" defaultValue="INTAKE" className="admin-input">
          <option>INTAKE</option>
          <option>ASSESSMENT</option>
          <option>ZOOM_NOTE</option>
          <option>UNKNOWN</option>
        </select>
        <input name="keyword_or_pattern" required placeholder="Keyword or regex pattern" className="admin-input" />
        <button className="rounded-xl bg-moss px-3 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-moss/90">Add rule</button>
      </form>
      <div className="mt-4 grid max-h-[360px] gap-2 overflow-auto pr-1">
        {rules.map((rule) => (
          <form key={rule.id} onSubmit={(event) => onSave(event, rule.id)} className="grid gap-2 rounded-2xl border border-line bg-white p-3 text-xs shadow-sm sm:grid-cols-[130px_1fr_86px_auto] sm:items-center">
            <select name="category" defaultValue={rule.category} className="admin-input">
              <option>INTAKE</option>
              <option>ASSESSMENT</option>
              <option>ZOOM_NOTE</option>
              <option>UNKNOWN</option>
            </select>
            <input name="keyword_or_pattern" defaultValue={rule.keyword_or_pattern} className="admin-input font-semibold" />
            <label className="flex items-center gap-2 font-semibold text-muted">
              <input name="is_active" type="checkbox" defaultChecked={rule.is_active} className="h-4 w-4 accent-moss" />
              Active
            </label>
            <button className="rounded-xl border border-line bg-cream px-3 py-2 font-bold text-moss transition hover:bg-sage">Save</button>
          </form>
        ))}
      </div>
    </Card>
  );
}

function AdminTemplatePreview({ templates, token }: { templates: AdminConfig["templates"]; token: string }) {
  const [templateId, setTemplateId] = useState(templates[0]?.id || "");
  const [preview, setPreview] = useState<TemplatePreview | null>(null);
  const selected = templates.find((template) => template.id === templateId) || templates[0];

  useEffect(() => {
    if (!selected) return;
    setTemplateId((current) => current || selected.id);
  }, [selected]);

  async function loadPreview() {
    if (!selected) return;
    const values = Object.fromEntries(selected.placeholders.slice(0, 30).map((placeholder) => [placeholder, `Sample ${placeholder.replaceAll("_", " ")}`]));
    setPreview(await apiFetch<TemplatePreview>(`/admin/templates/${selected.id}/preview-html`, token, { method: "POST", body: JSON.stringify({ values }) }));
  }

  async function openPdfPreview() {
    if (!selected) return;
    const values = Object.fromEntries(selected.placeholders.slice(0, 30).map((placeholder) => [placeholder, `Sample ${placeholder.replaceAll("_", " ")}`]));
    const response = await fetch(`${API_BASE}/admin/templates/${selected.id}/preview-pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ values })
    });
    if (!response.ok) return;
    const blob = await response.blob();
    window.open(URL.createObjectURL(blob), "_blank", "noopener,noreferrer");
  }

  return (
    <Card>
      <SectionHeader title="Template preview" subtitle="Inspect placeholders and render a cleaned sample from the backend template engine." />
      {selected ? (
        <div className="mt-4 grid gap-3">
          <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
            <select value={selected.id} onChange={(event) => { setTemplateId(event.target.value); setPreview(null); }} className="admin-input">
              {templates.map((template) => <option key={template.id} value={template.id}>{template.document_type} · {template.template_name} v{template.version}</option>)}
            </select>
            <div className="flex gap-2">
              <button onClick={loadPreview} className="rounded-xl bg-moss px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-moss/90">Render HTML</button>
              <button onClick={openPdfPreview} className="rounded-xl border border-line bg-white px-4 py-2 text-xs font-bold text-moss shadow-sm transition hover:bg-sage">Preview PDF</button>
            </div>
          </div>
          <div className="grid gap-2 rounded-2xl border border-line bg-cream p-3 text-xs text-muted">
            <div className="font-bold text-ink">{selected.placeholders.length} placeholders</div>
            <div className="max-h-20 overflow-auto leading-5">{selected.placeholders.slice(0, 60).join(", ")}</div>
          </div>
          {preview ? (
            <div className="grid gap-3">
              <div className="grid gap-2 sm:grid-cols-3">
                <Metric label="Missing" value={`${preview.missing_placeholders.length}`} />
                <Metric label="Unreplaced" value={`${preview.unreplaced_placeholders.length}`} />
                <Metric label="Cleanup" value={`${preview.cleanup_warnings.length} notes`} />
              </div>
              <iframe title="Template preview" srcDoc={preview.html} className="h-[340px] w-full rounded-2xl border border-line bg-white shadow-sm" />
              <details className="rounded-2xl border border-line bg-cream p-3 text-xs text-muted">
                <summary className="cursor-pointer font-bold text-ink">Raw vs cleaned HTML diagnostics</summary>
                <div className="mt-3 grid gap-3 lg:grid-cols-2">
                  <pre className="max-h-44 overflow-auto whitespace-pre-wrap rounded-xl bg-white p-3">{preview.raw_html || ""}</pre>
                  <pre className="max-h-44 overflow-auto whitespace-pre-wrap rounded-xl bg-white p-3">{preview.html}</pre>
                </div>
              </details>
            </div>
          ) : null}
        </div>
      ) : <Empty text="No templates registered yet." />}
    </Card>
  );
}

function AdminMiniTable({ title, subtitle, rows }: { title: string; subtitle: string; rows: string[][] }) {
  return (
    <Card>
      <SectionHeader title={title} subtitle={subtitle} />
      <div className="mt-4 overflow-hidden rounded-2xl border border-line">
        {rows.length ? rows.map((row, index) => (
          <div key={`${row[0]}-${index}`} className="grid grid-cols-[1fr_0.8fr_0.7fr] gap-3 border-b border-line bg-white px-3 py-3 text-xs last:border-b-0">
            <span className="truncate font-bold text-ink">{row[0]}</span>
            <span className="truncate text-muted">{row[1]}</span>
            <span className="truncate text-right font-semibold text-moss">{row[2]}</span>
          </div>
        )) : <div className="p-4 text-sm text-muted">No rows configured.</div>}
      </div>
    </Card>
  );
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`rounded-[1.35rem] border border-line/90 bg-white p-5 shadow-card transition duration-200 ${className}`}>{children}</section>;
}

function SectionHeader({ title, subtitle, eyebrow }: { title: string; subtitle: string; eyebrow?: string }) {
  return (
    <div>
      {eyebrow ? <div className="mb-1 text-[11px] font-bold uppercase tracking-[0.16em] text-moss">{eyebrow}</div> : null}
      <h2 className="text-lg font-bold tracking-tight">{title}</h2>
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

function Metric({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-line bg-cream px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.75)]">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted">{icon ? <span className="text-moss">{icon}</span> : null}{label}</div>
      <div className="mt-1 truncate text-sm font-bold text-ink">{value}</div>
    </div>
  );
}

function ActionButton({ children, onClick, disabled, tone, icon, subtext }: { children: React.ReactNode; onClick: () => void; disabled?: boolean; tone: "primary" | "secondary" | "accent"; icon?: React.ReactNode; subtext?: string }) {
  const toneClass = tone === "primary" ? "bg-moss text-white hover:bg-moss/90" : tone === "accent" ? "border-clay/25 bg-clay/10 text-clay hover:bg-clay/15" : "border-line bg-white text-ink hover:bg-cream";
  return (
    <button disabled={disabled} onClick={onClick} className={`focus-ring group grid grid-cols-[34px_minmax(0,1fr)] items-center gap-3 rounded-2xl border px-4 py-3 text-left text-sm font-semibold shadow-sm transition duration-200 hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-45 ${toneClass}`}>
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/20">{icon}</span>
      <span>
        <span className="block">{children}</span>
        {subtext ? <span className={`mt-0.5 block text-xs font-medium ${tone === "primary" ? "text-white/75" : "text-muted"}`}>{subtext}</span> : null}
      </span>
    </button>
  );
}

function CopyButton({ text, label, icon }: { text: string; label: string; icon?: React.ReactNode }) {
  return (
    <button onClick={() => copyToClipboard(text)} className="focus-ring inline-flex items-center gap-2 rounded-xl border border-line bg-white px-4 py-2.5 text-sm font-semibold shadow-sm transition hover:-translate-y-0.5 hover:bg-cream">
      {icon || <Clipboard size={16} />}
      {label}
    </button>
  );
}

function UtilityButton({ label, icon, disabled = false }: { label: string; icon: React.ReactNode; disabled?: boolean }) {
  return (
    <button disabled={disabled} type="button" className="focus-ring inline-flex items-center gap-2 rounded-xl border border-line bg-white px-4 py-2.5 text-sm font-semibold text-muted shadow-sm transition hover:-translate-y-0.5 hover:bg-cream disabled:cursor-not-allowed disabled:opacity-45">
      {icon}
      {label}
    </button>
  );
}

function OptionCard({ label, title, value, recommended }: { label: string; title: string; value: string; recommended: boolean }) {
  return (
    <div className={`rounded-2xl border p-4 ${recommended ? "border-moss/30 bg-sage shadow-sm" : "border-line bg-cream"}`}>
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-bold uppercase tracking-[0.16em] text-muted">{label}</span>
        {recommended ? <StatusBadge value="READY" /> : null}
      </div>
      <div className="mt-3 text-base font-bold">{title}</div>
      <div className="mt-1 text-2xl font-bold text-moss">{value}</div>
    </div>
  );
}

function Initials({ name, small = false }: { name: string; small?: boolean }) {
  const initials = name.split(" ").filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "PT";
  return <span className={`flex shrink-0 items-center justify-center rounded-2xl bg-moss text-sm font-bold text-white shadow-sm ring-4 ring-moss/10 ${small ? "h-9 w-9" : "h-16 w-16 text-lg"}`}>{initials}</span>;
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

function shortMrn(patient: Patient) {
  return `MRN-${patient.id.slice(0, 6).toUpperCase()}`;
}

function recentActivity(patient: Patient) {
  const latest = [...patient.output_documents].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0];
  if (latest) return `${latest.doc_type.replace("_", " ")} ${latest.status.toLowerCase()}`;
  const source = [...patient.source_documents].sort((a, b) => Date.parse(b.uploaded_at) - Date.parse(a.uploaded_at))[0];
  if (source) return `${source.file_type.replace("_", " ")} received`;
  return "No recent activity";
}

function documentLabel(source: SourceDocument) {
  const labels: Record<string, string> = {
    INTAKE: "Intake packet",
    ASSESSMENT: "Assessment / rating scale",
    ZOOM_NOTE: "Zoom note",
    UNKNOWN: "Unclassified document"
  };
  return labels[source.file_type] || "Clinical document";
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
