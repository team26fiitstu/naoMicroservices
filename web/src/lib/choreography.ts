import { api } from "@/lib/api";

// state is saved exercise placed in graph, x and y only for editor
export type ChoreographyState = { state_id: string; label: string; x: number; y: number };
type Transition = { id: string; from: string; to: string; label: string };

export type Choreography = {
  id: string;
  name: string;
  initial_state: string;
  states: ChoreographyState[];
  transitions: Transition[];
  created_at: string;
  updated_at: string;
};

export type ChoreographySummary = Pick<Choreography, "id" | "name" | "created_at" | "updated_at"> & { state_count: number };

// what side panel shows, transitions selectable for transition editing
export type GraphSelection = { kind: "state" | "transition"; id: string } | null;

const GRID_COLUMNS = 4;
const GRID_STEP = { x: 240, y: 120 };

// first grid cell no state is near, so new state does not cover moved or remaining ones
export function nextStatePosition(states: ChoreographyState[]) {
  const taken = (x: number, y: number) =>
    states.some((s) => Math.abs(s.x - x) < GRID_STEP.x && Math.abs(s.y - y) < GRID_STEP.y);
  for (let cell = 0; ; cell++) {
    const x = (cell % GRID_COLUMNS) * GRID_STEP.x;
    const y = Math.floor(cell / GRID_COLUMNS) * GRID_STEP.y;
    if (!taken(x, y)) return { x, y };
  }
}

type GraphFields = Pick<Choreography, "name" | "initial_state" | "states" | "transitions">;

// label of state by id, id itself when state is gone
export const stateLabel = (graph: Choreography, stateId: string) =>
  graph.states.find((s) => s.state_id === stateId)?.label ?? stateId;

export const listChoreographies = () => api<ChoreographySummary[]>("/choreography/list");

export const getChoreography = (id: string) => api<Choreography>(`/choreography/${id}`);

export const createChoreography = (graph: GraphFields) =>
  api<Choreography>("/choreography/create", { method: "POST", json: graph });

// whole graph replaced, server keeps id and timestamps
export const saveChoreography = ({ id, name, initial_state, states, transitions }: Choreography) =>
  api<Choreography>(`/choreography/${id}`, { method: "PUT", json: { name, initial_state, states, transitions } });

// list has no graph, so it is loaded first
export async function renameChoreography(id: string, name: string) {
  return saveChoreography({ ...(await getChoreography(id)), name });
}

export const deleteChoreography = (id: string) => api(`/choreography/${id}`, { method: "DELETE" });
