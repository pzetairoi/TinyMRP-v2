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
