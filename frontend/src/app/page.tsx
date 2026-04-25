"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Activity, Clipboard, FilePlus2, RefreshCw, Search } from "lucide-react";
import { LoginPanel } from "@/components/login-panel";
import { StatusBadge } from "@/components/status-badge";
import { apiFetch, BillingSummary, Patient } from "@/lib/api";

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [billing, setBilling] = useState<BillingSummary | null>(null);
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

  return (
    <main className="min-h-screen">
      <header className="border-b border-line bg-paper px-5 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-normal">Clinical AI Webapp</h1>
            <p className="text-sm text-stone-600">Drive intake, note generation, review, and Headway-ready billing.</p>
          </div>
          <div className="flex items-center gap-2 text-sm font-semibold text-moss">
            <Activity size={18} />
            Production scaffold
          </div>
        </div>
      </header>

      {!token ? <LoginPanel onToken={(value) => { setToken(value); load(value); }} /> : null}
      {error ? <div className="mx-auto mt-4 max-w-7xl rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

      <section className="mx-auto grid max-w-7xl gap-5 p-5 lg:grid-cols-[360px_1fr]">
        <aside className="grid content-start gap-4">
          <form onSubmit={createPatient} className="grid gap-3 rounded-md border border-line bg-white p-4 shadow-soft">
            <div className="flex items-center gap-2 font-semibold">
              <FilePlus2 size={18} />
              New patient
            </div>
            <input name="name" required placeholder="Patient name" className="focus-ring rounded-md border border-line px-3 py-2" />
            <input name="drive_folder_id" required placeholder="Drive folder ID" className="focus-ring rounded-md border border-line px-3 py-2" />
            <button className="focus-ring rounded-md bg-clinic px-4 py-2 font-semibold text-white">Create</button>
          </form>

          <div className="rounded-md border border-line bg-white shadow-soft">
            <div className="flex items-center gap-2 border-b border-line p-3">
              <Search size={16} />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search patients" className="w-full outline-none" />
            </div>
            <div className="max-h-[520px] overflow-auto">
              {filtered.map((patient) => (
                <button key={patient.id} onClick={() => setSelectedId(patient.id)} className={`w-full border-b border-line p-4 text-left hover:bg-paper ${patient.id === selectedId ? "bg-paper" : "bg-white"}`}>
                  <div className="font-semibold">{patient.name}</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <StatusBadge value={patient.source_documents.some((doc) => doc.file_type === "INTAKE") ? "INTAKE" : "UNKNOWN"} />
                    <StatusBadge value={patient.output_documents.at(-1)?.status || "DRAFT"} />
                  </div>
                </button>
              ))}
            </div>
          </div>
        </aside>

        <section className="min-w-0">
          {selected ? (
            <div className="grid gap-5">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
                <div>
                  <h2 className="text-xl font-semibold">{selected.name}</h2>
                  <p className="text-sm text-stone-600">Drive folder {selected.drive_folder_id}</p>
                </div>
                <button onClick={resyncDemoFiles} className="focus-ring inline-flex items-center gap-2 rounded-md border border-line bg-white px-4 py-2 font-semibold">
                  <RefreshCw size={16} />
                  Resync sample files
                </button>
              </div>

              <div className="grid gap-5 xl:grid-cols-2">
                <Panel title="Source Documents">
                  <div className="grid gap-2">
                    {selected.source_documents.map((source) => (
                      <div key={source.id} className="flex items-center justify-between gap-3 rounded-md border border-line p-3">
                        <span className="min-w-0 truncate">{source.name}</span>
                        <StatusBadge value={source.file_type} />
                      </div>
                    ))}
                    {!selected.source_documents.length ? <Empty text="No source documents synced yet." /> : null}
                  </div>
                </Panel>

                <Panel title="Generation">
                  <div className="grid gap-3">
                    <button onClick={() => generate(`/patients/${selected.id}/generate/summary`, { save_pdf: false })} className="focus-ring rounded-md bg-ink px-4 py-2 font-semibold text-white">Generate summary draft</button>
                    <button
                      onClick={() => {
                        const zoom = selected.source_documents.find((doc) => doc.file_type === "ZOOM_NOTE");
                        if (zoom) generate(`/patients/${selected.id}/generate/session-note`, { source_document_id: zoom.id, save_pdf: false });
                      }}
                      className="focus-ring rounded-md bg-moss px-4 py-2 font-semibold text-white"
                    >
                      Generate session note
                    </button>
                    <button onClick={() => generate(`/patients/${selected.id}/generate/treatment-plan`, { save_pdf: false })} className="focus-ring rounded-md bg-clinic px-4 py-2 font-semibold text-white">Generate treatment plan</button>
                  </div>
                </Panel>
              </div>

              <Panel title="Generated Outputs">
                <div className="grid gap-3">
                  {selected.output_documents.map((output) => (
                    <article key={output.id} className="rounded-md border border-line bg-white p-4">
                      <div className="mb-2 flex items-center justify-between gap-3">
                        <h3 className="font-semibold">{output.doc_type.replace("_", " ")}</h3>
                        <StatusBadge value={output.status} />
                      </div>
                      <p className="line-clamp-3 whitespace-pre-line text-sm text-stone-700">{output.content}</p>
                    </article>
                  ))}
                  {!selected.output_documents.length ? <Empty text="Generated drafts will appear here." /> : null}
                </div>
              </Panel>

              <Panel title="Billing Summary">
                {billing ? (
                  <div className="grid gap-3">
                    <div className="rounded-md border border-line bg-paper p-3 text-sm">{billing.headway_block}</div>
                    <button onClick={() => navigator.clipboard.writeText(billing.headway_block)} className="focus-ring inline-flex w-fit items-center gap-2 rounded-md border border-line bg-white px-4 py-2 font-semibold">
                      <Clipboard size={16} />
                      Copy Headway block
                    </button>
                  </div>
                ) : (
                  <Empty text="Generate a session note to create billing." />
                )}
              </Panel>
            </div>
          ) : (
            <Empty text="Create or select a patient to begin." />
          )}
        </section>
      </section>
    </main>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-md border border-line bg-white p-4 shadow-soft">
      <h2 className="mb-4 text-base font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-md border border-dashed border-line bg-white/60 p-6 text-center text-sm text-stone-500">{text}</div>;
}
