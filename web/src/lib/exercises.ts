import { api } from "@/lib/api";
import { appendVideoRange, type VideoRange } from "@/lib/videoRange";

// What exercise was built from, "poses" means robot commands only
export type ExerciseSource = "video" | "image" | "poses";

export type ExerciseSummary = {
  id: string;
  name: string;
  frame_count: number;
  created_at: string;
  repetitions: number;
  calories?: number | null;
  description?: string | null;
  source: ExerciseSource;
};

// Saved exercise fields changed from editor and exercise list
type ExerciseUpdate = { name?: string; calories?: number; description?: string };

// Video processing used by editor and choreography: one frame per second, at most 8 frames
export const DEFAULT_VIDEO_SETTINGS = { fps: 1, maxFrames: 8 };

// Exercise name from uploaded file name without extension
export const nameFromFile = (file: File) => file.name.replace(/\.[^/.]+$/, "");

export const listExercises = () => api<ExerciseSummary[]>("/exercise/list");

export const updateExercise = (id: string, fields: ExerciseUpdate) =>
  api(`/exercise/${id}/config`, { method: "PUT", json: fields });

// no body, repetitions from exercise config
export const runExercise = (id: string) => api(`/exercise/${id}/run`, { method: "POST" });

// Exercise from video part, fields like name, fps, max_frames passed to translator as is
export function createExerciseFromVideo(file: File, range: VideoRange | null, fields: Record<string, string | number> = {}) {
  const form = new FormData();
  form.append("video", file);
  for (const [key, value] of Object.entries(fields)) form.append(key, String(value));
  appendVideoRange(form, range);
  return api<{ id: string }>("/exercise/from_video", { method: "POST", body: form });
}

export function createExerciseFromImage(file: File, name: string) {
  const form = new FormData();
  form.append("image", file);
  form.append("name", name);
  return api<{ id: string }>("/exercise/from_image", { method: "POST", body: form });
}
