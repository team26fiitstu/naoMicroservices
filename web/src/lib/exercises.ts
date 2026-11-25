import { api } from "@/lib/api";

// Saved exercise fields changed from editor and exercise list
export type ExerciseUpdate = { name?: string; calories?: number; description?: string };

export const updateExercise = (id: string, fields: ExerciseUpdate) =>
  api(`/exercise/${id}/config`, { method: "PUT", json: fields });

// no body, repetitions from exercise config
export const runExercise = (id: string) => api(`/exercise/${id}/run`, { method: "POST" });
