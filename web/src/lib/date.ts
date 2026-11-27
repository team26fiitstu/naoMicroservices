// Server timestamps are UTC, older ones without timezone suffix
export const formatDateTime = (value: string) =>
  new Date(/Z|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`).toLocaleString("sk-SK", {
    day: "numeric", month: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
