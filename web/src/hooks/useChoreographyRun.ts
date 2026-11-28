import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { currentRun, getRun, gotoState, runErrorText, signalRun, startRun, stopRun, type RunSnapshot } from "@/lib/choreographyRun";
import { conflictText, failureText } from "@/lib/errors";
import type { StatusType } from "@/hooks/useStatus";

const POLL_MS = 1000;
const WAIT_FOR_STATE = "Počkajte, kým robot dokončí aktuálny stav.";

// run of this choreography, polled while active, null when none
export function useChoreographyRun(choreographyId: string, showStatus: (type: StatusType, text: string) => void) {
  const [run, setRun] = useState<RunSnapshot | null>(null);
  const [sending, setSending] = useState(false);
  // bumped by every action, poll answers started before it are outdated
  const version = useRef(0);
  // canvas clicks ignore disabled state, so second request blocked here
  const busy = useRef(false);

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
      const started = version.current;
      getRun(runId)
        .then((snapshot) => { if (started === version.current) apply(snapshot); })
        .catch((err) => {
          // run gone, e.g. translator restarted, page back to editing
          if (err instanceof ApiError && err.status === 404) {
            setRun(null);
            showStatus("error", "Choreografia už nebeží.");
          } else {
            showStatus("error", failureText("Načítanie stavu zlyhalo", err));
          }
        });
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [runId, apply, showStatus]);

  const send = async (request: () => Promise<RunSnapshot>, action: string, conflict: string) => {
    if (busy.current) return;
    busy.current = true;
    version.current += 1;
    setSending(true);
    try {
      apply(await request());
    } catch (err) {
      showStatus("error", conflictText(action, err, conflict));
    } finally {
      busy.current = false;
      setSending(false);
    }
  };

  const start = () =>
    send(() => startRun(choreographyId), "Spustenie zlyhalo", "Robot je zaneprázdnený inou choreografiou alebo cvičením.");

  const signal = (transitionId: string) => {
    if (runId) send(() => signalRun(runId, transitionId), "Signál zlyhal", WAIT_FOR_STATE);
  };

  // state changed without robot moving
  const goto = (stateId: string) => {
    if (runId) send(() => gotoState(runId, stateId), "Presun zlyhal", WAIT_FOR_STATE);
  };

  const stop = () => {
    if (runId) send(() => stopRun(runId), "Zastavenie zlyhalo", "Choreografia už je zastavená.");
  };

  return { run, sending, start, signal, goto, stop };
}
