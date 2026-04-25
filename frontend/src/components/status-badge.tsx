const styles: Record<string, string> = {
  DRAFT: "border-amber/25 bg-amber/10 text-amber",
  FINAL: "border-moss/25 bg-sage text-moss",
  ERROR: "border-red-300 bg-red-50 text-red-700",
  INTAKE: "border-moss/25 bg-sage text-moss",
  ASSESSMENT: "border-ink/15 bg-white text-ink",
  ZOOM_NOTE: "border-clay/25 bg-clay/10 text-clay",
  UNKNOWN: "border-line bg-white text-muted",
  READY: "border-moss/25 bg-sage text-moss",
  PENDING: "border-amber/25 bg-amber/10 text-amber",
  INACTIVE: "border-line bg-white text-muted",
  REVIEW: "border-clay/25 bg-clay/10 text-clay"
};

export function StatusBadge({ value }: { value: string }) {
  return (
    <span className={`inline-flex h-7 items-center rounded-full border px-3 text-xs font-semibold ${styles[value] || styles.UNKNOWN}`}>
      {value.replace("_", " ")}
    </span>
  );
}
