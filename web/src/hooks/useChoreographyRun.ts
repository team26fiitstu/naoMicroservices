import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { currentRun, getRun, gotoState, runErrorText, signalRun, startRun, stopRun, type RunSnapshot } from "@/lib/choreographyRun";
import { failureText } from "@/lib/errors";
import type { StatusType } from "@/hooks/useStatus";

const POLL_MS = 1000;

// 409 means robot or run not ready, server text is technical English
const runFailureText = (action: string, err: unknown, busy: string) =>
  err instanceof ApiError && err.status === 409 ? busy : failureText(action, err);

// run of this choreography, polled while active, null when none
export function useChoreographyRun(choreographyId: string, showStatus: (type: StatusType, text: string) => void) {
  const [run, setRun] = useState<RunSnapshot | null>(null);
  const [sending, setSending] = useState(false);

  // stopped run reported once and cleared, so graph goes back to editing
  const apply = useCallback((snapshot: RunSnapshot | null) => {
    if (snapshot?.status === "stopped") {
      if (snapshot.error) showStatus("error", `Choreografia zastavená. ${runErrorText(snapshot.error)}`);
      else showStatus("success", "Choreografia zastavená.");
      setRun(null);
    } else {
      setRun(snapshot);
    }
  }, [showStatus]);

  // run already active after page reload
  useEffect(() => {
    currentRun()
      .then((snapshot) => { if (snapshot?.choreography_id === choreographyId) apply(snapshot); })
      .catch(() => {/* run state unknown, page stays in editing */});
  }, [choreographyId, apply]);

  const runId = run?.run_id;
  useEffect(() => {
    if (!runId) return;
    const timer = setInterval(() => {
      getRun(runId).then(apply).catch((err) => showStatus("error", failureText("Načítanie stavu zlyhalo", err)));
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [runId, apply, showStatus]);

  const send = async (request: () => Promise<RunSnapshot>, action: string, busy: string) => {
    setSending(true);
    try {
      apply(await request());
    } catch (err) {
      showStatus("error", runFailureText(action, err, busy));
    } finally {
      setSending(false);
    }
  };

  const start = () =>
    send(() => startRun(choreographyId), "Spustenie zlyhalo", "Robot je zaneprázdnený inou choreografiou alebo cvičením.");
  const signal = (transitionId: string) =>
    runId && send(() => signalRun(runId, transitionId), "Signál zlyhal", "Počkajte, kým robot dokončí aktuálny stav.");
  const goto = (stateId: string) =>
    runId && send(() => gotoState(runId, stateId), "Presun zlyhal", "Počkajte, kým robot dokončí aktuálny stav.");
  const stop = () => runId && send(() => stopRun(runId), "Zastavenie zlyhalo", "Choreografia už je zastavená.");

  return { run, sending, start, signal, goto, stop };
}
