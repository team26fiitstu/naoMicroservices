import { ApiError } from "@/lib/api";

// "Nahranie zlyhalo: HTTP 502"
export const failureText = (action: string, err: unknown) =>
  `${action}: ${err instanceof Error ? err.message : String(err)}`;

export const robotCommandFailureText = (action: string, err: unknown) =>
  err instanceof ApiError && err.status === 409
    ? "Robot práve vykonáva choreografiu. Skúste to znova po jej skončení."
    : failureText(action, err);
