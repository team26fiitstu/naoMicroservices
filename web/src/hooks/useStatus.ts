import { useCallback, useRef, useState } from "react";

export type StatusType = "success" | "error" | "info";
export type Status = { type: StatusType; text: string } | null;

// Page status message, success and info hide after delay, errors stay
export function useStatus(hideAfterMs = 4000) {
  const [status, setStatus] = useState<Status>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = useCallback((type: StatusType, text: string) => {
    if (timer.current) clearTimeout(timer.current);
    setStatus({ type, text });
    if (type !== "error") timer.current = setTimeout(() => setStatus(null), hideAfterMs);
  }, [hideAfterMs]);

  const clear = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    setStatus(null);
  }, []);

  return { status, show, clear };
}
