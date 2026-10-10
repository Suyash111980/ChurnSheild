export function isNonEmpty(value) { return typeof value === "string" && value.trim().length > 0; }
export function isRiskCategory(value) { return ["low", "medium", "high"].includes(value); }
