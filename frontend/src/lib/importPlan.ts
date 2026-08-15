/**
 * Presentation helpers for the import-plan preview.
 *
 * Extracted from UploadPackPage so they can be tested directly: the plan is
 * how an operator decides whether to run an import, and a value rendered as
 * blank or an action coloured as safe would both mislead that decision.
 */

/** Render any plan value for display, never returning an empty cell. */
export function valueText(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    // Circular structures still need to show something.
    return String(value);
  }
}

/** Colour class for a planned action. Destructive actions must read as such. */
export function actionClass(action: string): string {
  if (action === "add") return "text-success";
  if (["remove", "replace", "clear"].includes(action)) return "text-danger";
  if (["blocked", "skipped"].includes(action)) return "text-warning";
  if (["change", "quantity_change"].includes(action)) return "text-primary";
  return "text-muted";
}

/** What the operator picks: add nothing over the top, or let the pack win. */
export type Tier = "add" | "overwrite";
/** Per-category override of the tier, from the advanced panel. */
export type CategoryMode = "skip" | "add" | "overwrite";
export type DataMode = "skip" | "fill_blanks" | "replace_unapproved" | "replace_all";
export type BomMode = "skip" | "fill_if_empty" | "replace_unapproved" | "replace_all";
export type FileMode = "skip" | "add_missing" | "replace_unapproved" | "replace_all";
export type ApprovalMode = "preserve" | "import_unapproved" | "replace_all";

const CATEGORY_MODES: Record<
  CategoryMode,
  { data: DataMode; bom: BomMode; file: FileMode }
> = {
  skip: { data: "skip", bom: "skip", file: "skip" },
  add: { data: "fill_blanks", bom: "fill_if_empty", file: "add_missing" },
  overwrite: { data: "replace_unapproved", bom: "replace_unapproved", file: "replace_unapproved" },
};
const OVERRIDDEN: Record<CategoryMode, { data: DataMode; bom: BomMode; file: FileMode }> = {
  skip: CATEGORY_MODES.skip,
  add: CATEGORY_MODES.add,
  overwrite: { data: "replace_all", bom: "replace_all", file: "replace_all" },
};

// Approval is not a policy of its own: it is read out of the pack. Adding still
// records a release, because publishing an approval from CAD does not destroy
// anything; removing one, or editing an approved part, needs the override.
const APPROVAL_FOR_DATA: Record<DataMode, ApprovalMode> = {
  skip: "preserve",
  fill_blanks: "import_unapproved",
  replace_unapproved: "import_unapproved",
  replace_all: "replace_all",
};

/**
 * Translate the two-choice UI into the four modes the API takes.
 *
 * This is the one place where a mistake silently overwrites approved data, so
 * the override can only be reached by holding the permission AND ticking the
 * box AND that category actually overwriting.
 */
export function resolveModes(input: {
  tier: Tier;
  categories?: Partial<Record<"data" | "bom" | "file", CategoryMode | null>>;
  includeApproved?: boolean;
  canOverride?: boolean;
}): { data_mode: DataMode; bom_mode: BomMode; file_mode: FileMode; approval_mode: ApprovalMode } {
  const pick = (key: "data" | "bom" | "file"): CategoryMode =>
    input.categories?.[key] ?? input.tier;
  const override = !!input.includeApproved && !!input.canOverride;
  const table = override ? OVERRIDDEN : CATEGORY_MODES;
  const data = table[pick("data")].data;
  return {
    data_mode: data,
    bom_mode: table[pick("bom")].bom,
    file_mode: table[pick("file")].file,
    approval_mode: APPROVAL_FOR_DATA[data],
  };
}

export type PlanPartLike = {
  target_state: "new" | "existing_unapproved" | "existing_approved";
  changed: boolean;
  blocked: boolean;
  allowed: boolean;
};

/** The outcome groups the redline is organised by. */
export type GroupKey = "blocked" | "modified_approved" | "new" | "changed" | "unchanged";

/**
 * Which group a part belongs to.
 *
 * Order is deliberate: anything the operator must decide about outranks what
 * merely happened, so a blocked approved part is found under Blocked rather
 * than hiding among a hundred untouched rows.
 */
export function groupOf(part: PlanPartLike): GroupKey {
  if (part.blocked || !part.allowed) return "blocked";
  if (part.target_state === "existing_approved" && part.changed) return "modified_approved";
  if (part.target_state === "new") return "new";
  if (part.changed) return "changed";
  return "unchanged";
}
