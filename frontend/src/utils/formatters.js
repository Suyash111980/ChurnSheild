export const formatPercent = (value) => `${Math.round(Number(value) * 100)}%`;
export const formatDate = (value) => value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value)) : "—";
export const formatNumber = (value) => new Intl.NumberFormat().format(Number(value) || 0);
