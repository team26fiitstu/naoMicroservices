import { useCallback, useEffect, useRef, useState } from "react";
import { getChoreography, nextStatePosition, saveChoreography, type Choreography } from "@/lib/choreography";
import { listExercises, updateExercise, type ExerciseSummary } from "@/lib/exercises";
import { exerciseDisplayName } from "@/lib/exerciseName";
import { failureText } from "@/lib/errors";
import { useStatus } from "@/hooks/useStatus";

// state label mirrors exercise name, null when all labels already match
function syncLabels(graph: Choreography, exercises: ExerciseSummary[]): Choreography | null {
  const names = new Map(exercises.map((e) => [e.id, exerciseDisplayName(e.name)]));
  const states = graph.states.map((s) => {
    const name = names.get(s.state_id);
    return name && name !== s.label ? { ...s, label: name } : s;
  });
  return states.some((s, i) => s !== graph.states[i]) ? { ...graph, states } : null;
}

// choreography graph with its exercises, every change saved as whole graph
export function useChoreography(id: string) {
  const [graph, setGraph] = useState<Choreography | null>(null);
  const [exercises, setExercises] = useState<ExerciseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const { status, show: showStatus } = useStatus();
  // latest graph for changes made after awaits, render closure may be stale
  const latest = useRef<Choreography | null>(null);

  const show = (next: Choreography | null) => {
    latest.current = next;
    setGraph(next);
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [loaded, list] = await Promise.all([getChoreography(id), listExercises()]);
      // exercise renamed elsewhere, label follows it
      const synced = syncLabels(loaded, list);
      latest.current = synced ?? loaded;
      setGraph(latest.current);
      setExercises(list);
      setFailed(false);
      if (synced) saveChoreography(synced).catch((err) => showStatus("error", failureText("Uloženie zlyhalo", err)));
    } catch (err) {
      showStatus("error", failureText("Načítanie choreografie zlyhalo", err));
      setFailed(!latest.current);
    } finally {
      setLoading(false);
    }
  }, [id, showStatus]);

  useEffect(() => { load(); }, [load]);

  // change applied to latest graph, shown at once, server copy reloaded when save fails
  const update = async (change: (graph: Choreography) => Choreography) => {
    if (!latest.current) return false;
    const next = change(latest.current);
    show(next);
    try {
      await saveChoreography(next);
      return true;
    } catch (err) {
      showStatus("error", failureText("Uloženie zlyhalo", err));
      load();
      return false;
    }
  };

  const rename = (name: string) => update((g) => ({ ...g, name }));

  // renames exercise itself, label in graph follows
  const renameState = async (stateId: string, name: string) => {
    try {
      await updateExercise(stateId, { name });
    } catch (err) {
      showStatus("error", failureText("Premenovanie zlyhalo", err));
      return false;
    }
    setExercises((list) => list.map((e) => (e.id === stateId ? { ...e, name } : e)));
    return update((g) => ({ ...g, states: g.states.map((s) => (s.state_id === stateId ? { ...s, label: name } : s)) }));
  };

  const moveState = (stateId: string, x: number, y: number) =>
    update((g) => ({ ...g, states: g.states.map((s) => (s.state_id === stateId ? { ...s, x, y } : s)) }));

  const addState = (exercise: Pick<ExerciseSummary, "id" | "name">) =>
    update((g) => g.states.some((s) => s.state_id === exercise.id) ? g : {
      ...g,
      states: [...g.states, { state_id: exercise.id, label: exerciseDisplayName(exercise.name), ...nextStatePosition(g.states) }],
    });

  // exercise created outside graph, list refreshed for its type, state added even if refresh fails
  const addNewExercise = async (exercise: Pick<ExerciseSummary, "id" | "name">) => {
    try {
      setExercises(await listExercises());
    } catch (err) {
      showStatus("error", failureText("Načítanie cvičení zlyhalo", err));
    }
    return addState(exercise);
  };

  // NOTE: temporary, for convenience and testing, transitions are SCRUM-96
  const renameTransition = (transitionId: string, label: string) =>
    update((g) => ({ ...g, transitions: g.transitions.map((t) => (t.id === transitionId ? { ...t, label } : t)) }));

  // initial state stays, graph needs it
  const removeState = (stateId: string) =>
    update((g) => stateId === g.initial_state ? g : {
      ...g,
      states: g.states.filter((s) => s.state_id !== stateId),
      transitions: g.transitions.filter((t) => t.from !== stateId && t.to !== stateId),
    });

  const setInitialState = (stateId: string) => update((g) => ({ ...g, initial_state: stateId }));

  return { graph, exercises, loading, failed, reload: load, status, showStatus, rename, renameState, renameTransition, moveState, addState, addNewExercise, removeState, setInitialState };
}
