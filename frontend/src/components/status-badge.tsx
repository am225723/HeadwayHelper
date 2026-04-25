const styles: Record<string, string> = {
  DRAFT: "border-clinic/30 bg-clinic/10 text-clinic",
  FINAL: "border-moss/30 bg-moss/10 text-moss",
  ERROR: "border-red-300 bg-red-50 text-red-700",
  INTAKE: "border-moss/30 bg-white text-moss",
  ASSESSMENT: "border-ink/20 bg-white text-ink",
  ZOOM_NOTE: "border-clinic/30 bg-white text-clinic",
  UNKNOWN: "border-line bg-white text-stone-500"
};

export function StatusBadge({ value }: { value: string }) {
  return (
    <span className={`inline-flex h-7 items-center rounded-full border px-3 text-xs font-semibold ${styles[value] || styles.UNKNOWN}`}>
      {value.replace("_", " ")}
    </span>
  );
}
