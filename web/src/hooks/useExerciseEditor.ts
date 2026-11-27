import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { askLlm, LLM_AVAILABLE } from "@/lib/llm";
import { failureText } from "@/lib/errors";
import { createExerciseFromVideo, runExercise, updateExercise } from "@/lib/exercises";
import { pluralSk } from "@/lib/plural";
import { poseLabel, type PoseCommand } from "@/lib/poses";
import type { VideoRange } from "@/lib/videoRange";
import { motionSummary, normalizeFrame, type Frame, type RawFrame } from "@/lib/frames";
import { useStatus } from "@/hooks/useStatus";

export type UploadSettings = { fps: number; maxFrames: number };

// Exercise in editor: frames, AI estimates and all backend calls
export function useExerciseEditor(initialId: string | null) {
  const [exerciseId, setExerciseId] = useState(initialId);
  const [frames, setFrames] = useState<Frame[]>([]);
  const [poses, setPoses] = useState<PoseCommand[]>([]);
  const { status, show: showStatus, clear: clearStatus } = useStatus();
  const [uploading, setUploading] = useState(false);
  const [loadingFrames, setLoadingFrames] = useState(false);
  const [running, setRunning] = useState(false);
  const [insertingAt, setInsertingAt] = useState<number | null>(null);
  const [deletingAt, setDeletingAt] = useState<number | null>(null);
  const [exerciseName, setExerciseName] = useState("");
  const [calories, setCalories] = useState<number | null>(null);
  const [caloriesLoading, setCaloriesLoading] = useState(false);
  const [description, setDescription] = useState<string | null>(null);
  const [descLoading, setDescLoading] = useState(false);
  // frame idx to pose name, for frames inserted from pose registry
  const [poseFrameMap, setPoseFrameMap] = useState<Record<number, string>>({});

  const generateDescription = useCallback(async (id: string, frameList: Frame[]) => {
    if (!frameList.length || !LLM_AVAILABLE) return;
    setDescLoading(true);
    try {
      const { description: text } = await askLlm<{ description: string }>(
        `You are a fitness expert. Given NAO humanoid robot joint angle data for a physical exercise, write a short 1–2 sentence description in Slovak of what the exercise looks like and which body parts it involves. Return ONLY a JSON object: {"description": "<text>"}. Be concise and natural.`,
        motionSummary(frameList),
      );
      const desc = text?.trim();
      if (desc) {
        setDescription(desc);
        await updateExercise(id, { description: desc });
      }
    } catch {
      // best-effort, errors not shown
    } finally {
      setDescLoading(false);
    }
  }, []);

  const estimateCalories = useCallback(async (id: string, frameList: Frame[]) => {
    if (!frameList.length || !LLM_AVAILABLE) return;
    setCaloriesLoading(true);
    try {
      const { calories: estimate } = await askLlm<{ calories: number }>(
        `You are a fitness expert. Given NAO humanoid robot joint angle data for a physical exercise, estimate the calories a person would burn performing this exercise once. Return ONLY a JSON object: {"calories": <number>}. Round to one decimal place.`,
        motionSummary(frameList),
      );
      const kcal = Number(estimate);
      if (!isNaN(kcal) && kcal > 0) {
        setCalories(kcal);
        await updateExercise(id, { calories: kcal });
      }
    } catch {
      // best-effort, errors not shown
    } finally {
      setCaloriesLoading(false);
    }
  }, []);

  // frames, then name and stored estimates, missing estimates generated
  const loadFrames = useCallback(async (id: string, quiet = false): Promise<Frame[]> => {
    setLoadingFrames(true);
    try {
      const data = await api<RawFrame[] | { frames?: RawFrame[] }>(`/exercise/${id}/frames`);
      const loaded = (Array.isArray(data) ? data : data.frames ?? []).map(normalizeFrame);
      setFrames(loaded);
      // rebuilt from server so stale entries for reused indices don't bleed through
      setPoseFrameMap(Object.fromEntries(
        loaded.filter((f) => f.pose_name).map((f) => [f.idx, f.pose_name!]),
      ));
      api<{ name?: string; calories?: number; description?: string }>(`/exercise/${id}`)
        .then((cfg) => {
          if (cfg.name) setExerciseName(cfg.name);
          if (cfg.calories != null) setCalories(cfg.calories);
          else estimateCalories(id, loaded);
          if (cfg.description) setDescription(cfg.description);
          else generateDescription(id, loaded);
        })
        .catch(() => {});
      if (!quiet) showStatus("success", `${pluralSk(loaded.length, "Načítaná", "Načítané", "Načítaných")} ${loaded.length} ${pluralSk(loaded.length, "snímka", "snímky", "snímok")}.`);
      return loaded;
    } catch (err) {
      showStatus("error", failureText("Načítanie snímok zlyhalo", err));
      return [];
    } finally {
      setLoadingFrames(false);
    }
  }, [showStatus, estimateCalories, generateDescription]);

  // exercise from ?id= loaded once on open
  useEffect(() => {
    if (initialId) loadFrames(initialId);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    api<string[] | { commands?: string[] }>("/commands")
      .then((data) => {
        // string[], { commands: string[] } or keyed object
        const names = Array.isArray(data) ? data : Array.isArray(data.commands) ? data.commands : Object.keys(data);
        setPoses(names.map((name) => ({ name })));
      })
      .catch(() => {/* poses not critical at startup */});
  }, []);

  const upload = useCallback(async (file: File, range: VideoRange | null, { fps, maxFrames }: UploadSettings) => {
    setUploading(true);
    clearStatus();
    setFrames([]);
    setExerciseId(null);
    try {
      const { id } = await createExerciseFromVideo(file, range, { fps, max_frames: maxFrames });
      setExerciseId(id);
      showStatus("info", "Cvičenie vytvorené. Načítavam snímky…");
      await loadFrames(id);
      return true;
    } catch (err) {
      showStatus("error", failureText("Nahranie zlyhalo", err));
      return false;
    } finally {
      setUploading(false);
    }
  }, [showStatus, clearStatus, loadFrames]);

  // back to upload zone for new video
  const reset = () => {
    setExerciseId(null);
    setFrames([]);
    clearStatus();
    setExerciseName("");
    setCalories(null);
    setDescription(null);
  };

  // position is index in sequence where new frame goes
  const insertPose = useCallback(async (position: number, poseName: string) => {
    if (!exerciseId) return;
    setInsertingAt(position);
    const oldIdxs = new Set(frames.map((f) => f.idx));
    try {
      await api(`/exercise/${exerciseId}/frame/from_pose`, { method: "POST", json: { pose_name: poseName, position } });
      const newFrames = await loadFrames(exerciseId, true);
      const newFrame = newFrames.find((f) => !oldIdxs.has(f.idx));
      if (newFrame) setPoseFrameMap((prev) => ({ ...prev, [newFrame.idx]: poseName }));
      generateDescription(exerciseId, newFrames);
      showStatus("success", `Póza „${poseLabel(poseName)}“ vložená.`);
    } catch (err) {
      showStatus("error", failureText("Vloženie zlyhalo", err));
    } finally {
      setInsertingAt(null);
    }
  }, [exerciseId, frames, loadFrames, generateDescription, showStatus]);

  const deleteFrame = useCallback(async (frameIdx: number) => {
    if (!exerciseId) return;
    setDeletingAt(frameIdx);
    try {
      await api(`/exercise/${exerciseId}/frame/${frameIdx}`, { method: "DELETE" });
      const remaining = frames.filter((f) => f.idx !== frameIdx);
      setFrames(remaining);
      generateDescription(exerciseId, remaining);
      showStatus("success", "Snímka odstránená.");
    } catch (err) {
      showStatus("error", failureText("Odstránenie zlyhalo", err));
    } finally {
      setDeletingAt(null);
    }
  }, [exerciseId, frames, generateDescription, showStatus]);

  // new order shown at once, then saved
  const reorderFrames = useCallback(async (reordered: Frame[]) => {
    setFrames(reordered);
    if (!exerciseId) return;
    try {
      await api(`/exercise/${exerciseId}/sequence`, { method: "PUT", json: { frame_sequence: reordered.map((f) => f.idx) } });
      showStatus("success", "Poradie uložené.");
    } catch (err) {
      showStatus("error", failureText("Uloženie zlyhalo", err));
    }
  }, [exerciseId, showStatus]);

  // false when name was not saved
  const rename = useCallback(async (name: string) => {
    if (!exerciseId || !name.trim()) return false;
    try {
      await updateExercise(exerciseId, { name: name.trim() });
      setExerciseName(name.trim());
      return true;
    } catch (err) {
      showStatus("error", failureText("Premenovanie zlyhalo", err));
      return false;
    }
  }, [exerciseId, showStatus]);

  const run = useCallback(async () => {
    if (!exerciseId) return;
    setRunning(true);
    try {
      await runExercise(exerciseId);
      showStatus("success", "Cvičenie odoslané robotovi!");
    } catch (err) {
      showStatus("error", failureText("Spustenie zlyhalo", err));
    } finally {
      setRunning(false);
    }
  }, [exerciseId, showStatus]);

  return {
    exerciseId,
    // pose name from registry wins over server value
    frames: frames.map((f) => ({ ...f, pose_name: poseFrameMap[f.idx] ?? f.pose_name })),
    poses,
    status,
    showStatus,
    clearStatus,
    uploading,
    loadingFrames,
    running,
    insertingAt,
    deletingAt,
    exerciseName,
    calories,
    caloriesLoading,
    description,
    descLoading,
    loadFrames,
    upload,
    reset,
    insertPose,
    deleteFrame,
    reorderFrames,
    rename,
    run,
  };
}
