/** The fields the part-detail file helpers read.
 *
 * The first three drive grouping. name and rel_path are read when building
 * datasheet labels: the objects always carried them, but the type did not
 * declare them, so every use was an error TypeScript could not report while
 * the typecheck was not running.
 */
export type GroupableFile = {
  ext_group?: string
  group?: string
  ext?: string
  name?: string
  rel_path?: string
}

/**
 * File grouping and size formatting for part detail.
 *
 * Extracted from PartDetailPage. groupKeyOf collapses the several extensions
 * SolidWorks emits for one logical artefact (eprt/edr, stp/step, jpg/jpeg/png)
 * so the UI shows one row per artefact rather than per file extension.
 */

export function groupKeyOf(f: GroupableFile): string {
  const raw = (f.ext_group || f.group || f.ext || "others").toLowerCase();
  if (raw === "eprt" || raw === "edr") return "edr";
  if (raw === "stp" || raw === "step") return "step";
  if (raw === "jpg" || raw === "jpeg" || raw === "png") return "png";
  return raw;
}

// ---------- Check if value has display value ----------
export function hasDisplayValue(v: any): boolean {
  if (v === null || v === undefined) return false;
  if (typeof v === "string") return v.trim() !== "";
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === "object") return Object.keys(v).length > 0;
  return true;
}

export function groupFiles(files: GroupableFile[]) {
  const g: Record<string, GroupableFile[]> = {};
  for (const f of files || []) {
    const k = groupKeyOf(f);
    (g[k] ||= []).push(f);
  }
  return g;
}

export function formatBytes(value?: number): string {
  const num = Number(value || 0);
  if (!num) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let n = num;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i += 1;
  }
  return `${n.toFixed(n >= 10 ? 0 : 1)} ${units[i]}`;
}
