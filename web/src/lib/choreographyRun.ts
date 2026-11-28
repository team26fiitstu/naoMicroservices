import { api, ApiError } from "@/lib/api";
import type { Choreography } from "@/lib/choreography";

type Transition = Choreography["transitions"][number];

// run state from translator, outgoing transitions of current state included
export type RunSnapshot = {
  run_id: string;
  choreography_id: string;
  state_id: string;
  status: "performing" | "waiting" | "stopped";
  outgoing_transitions: Transition[];
  error: string | null;
};

export const startRun = (choreographyId: string) =>
  api<RunSnapshot>(`/choreography/${choreographyId}/run`, { method: "POST" });

// null when no run active
export const currentRun = () =>
  api<RunSnapshot>("/run/current").catch((err) => {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  });

export const getRun = (runId: string) => api<RunSnapshot>(`/run/${runId}`);

export const signalRun = (runId: string, transitionId: string) =>
  api<RunSnapshot>(`/run/${runId}/signal`, { method: "POST", json: { transition_id: transitionId } });

// state changed without poses and voice lines
export const gotoState = (runId: string, stateId: string) =>
  api<RunSnapshot>(`/run/${runId}/goto`, { method: "POST", json: { state_id: stateId } });

export const stopRun = (runId: string) => api<RunSnapshot>(`/run/${runId}/stop`, { method: "POST" });

// translator run errors are technical English, shown as one Slovak message
export const runErrorText = (error: string) =>
  error.includes("reservation")
    ? "Robot je zaneprázdnený inou úlohou."
    : "Robot stav nevykonal, skontrolujte jeho pripojenie.";
