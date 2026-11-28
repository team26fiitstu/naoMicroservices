import { ApiError } from "@/lib/api";

// "Nahranie zlyhalo: HTTP 502"
export const failureText = (action: string, err: unknown) =>
  `${action}: ${err instanceof Error ? err.message : String(err)}`;

// 409 means busy or not ready, own message instead of technical server text
export const conflictText = (action: string, err: unknown, message: string) =>
  err instanceof ApiError && err.status === 409 ? message : failureText(action, err);

export const robotCommandFailureText = (action: string, err: unknown) =>
  conflictText(action, err, "Robot práve vykonáva choreografiu. Skúste to znova po jej skončení.");
