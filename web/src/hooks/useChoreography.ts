import { useCallback, useEffect, useRef, useState } from "react";
import { getChoreography, newState, saveChoreography, type Choreography } from "@/lib/choreography";
import { exerciseDisplayName } from "@/lib/exerciseName";
import { listExercises, type ExerciseRef, type ExerciseSummary } from "@/lib/exercises";
import { failureText } from "@/lib/errors";
import { useStatus } from "@/hooks/useStatus";

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
      latest.current = loaded;
      setGraph(loaded);
      setExercises(list);
      setFailed(false);
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

  // label unique in graph, exercise itself keeps its name
  const renameState = (stateId: string, label: string) => {
    if (latest.current?.states.some((s) => s.id !== stateId && s.label === label)) {
      showStatus("error", `Stav „${label}“ už v choreografii je.`);
      return Promise.resolve(false);
    }
    return update((g) => ({ ...g, states: g.states.map((s) => (s.id === stateId ? { ...s, label } : s)) }));
  };

  const moveState = (stateId: string, x: number, y: number) =>
    update((g) => ({ ...g, states: g.states.map((s) => (s.id === stateId ? { ...s, x, y } : s)) }));

  const addState = (exercise: ExerciseRef) =>
    update((g) => ({ ...g, states: [...g.states, newState(g.states, exercise.id, exerciseDisplayName(exercise.name))] }));

  const changeExercise = (stateId: string, exerciseId: string) =>
    update((g) => ({ ...g, states: g.states.map((s) => (s.id === stateId ? { ...s, exercise_id: exerciseId } : s)) }));

  // copy with same exercise, label numbered, transitions not copied
  const duplicateState = (stateId: string) =>
    update((g) => {
      const state = g.states.find((s) => s.id === stateId);
      return state ? { ...g, states: [...g.states, newState(g.states, state.exercise_id, state.label)] } : g;
    });

  // exercise created outside graph, list refreshed for its type, state added even if refresh fails
  const addNewExercise = async (exercise: ExerciseRef) => {
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
      states: g.states.filter((s) => s.id !== stateId),
      transitions: g.transitions.filter((t) => t.from !== stateId && t.to !== stateId),
    });

  const setInitialState = (stateId: string) => update((g) => ({ ...g, initial_state: stateId }));

  return { graph, exercises, loading, failed, reload: load, status, showStatus, rename, renameState, renameTransition, moveState, addState, addNewExercise, removeState, setInitialState, changeExercise, duplicateState };
}
