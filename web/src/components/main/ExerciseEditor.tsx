import { useState, useRef, useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "radix-ui";
import { AudioRecorderComponent } from "@/components/ui/audioRecorder";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Loader2,
  Upload,
  Play,
  Trash2,
  GripVertical,
  AlertCircle,
  CheckCircle,
  Film,
  ChevronLeft,
  ChevronRight,
  Mic,
  MicOff,
  X,
  Pencil,
  Save
} from "lucide-react";

import "@/components/styles/toggle.css";

// ── pose display names (Slovak) ───────────────────────────────────
const POSE_DISPLAY_SK: Record<string, string> = {
  wave:        "Zamávaj",
  stand:       "Stoj",
  sit:         "Sed",
  hands_up:    "Ruky hore",
  t_pose:      "T-Póza",
  bow:         "Úklon",
  crouch:      "Drep",
  point_right: "Ukáž vpravo",
  point_left:  "Ukáž vľavo",
};

const NO_NAMING = true;
// ── API config ────────────────────────────────────────────────────
const UPLOAD_API = NO_NAMING? "http://localhost:7000" : ""; //empty for reverse proxy nginx
const EDITOR_API = NO_NAMING? "http://localhost:7001" : "";
const POSES_API  = NO_NAMING? "http://localhost:8000" : "";
const ROBOT_API  = NO_NAMING? "http://localhost:5000" : "";
const LLM_API_BASE = import.meta.env.VITE_LLM_API_BASE ?? "https://litellm.blockfinlab.xyz";
const LLM_API_KEY  = import.meta.env.VITE_LLM_API_KEY ?? "";
const LLM_MODEL    = "gpt-5.4-fiit";
const LLM_AVAILABLE = !!LLM_API_KEY;

// ── types ─────────────────────────────────────────────────────────
type Frame = {
  idx: number;
  angles: Record<string, number>;
  keypoints?: Record<string, unknown>;
  nao_angles?: number[];
  pose_name?: string;
};

type PoseCommand = {
  name: string;
};

type StatusMsg = { type: "success" | "error" | "info"; text: string } | null;

// ── drag-reorder hook ─────────────────────────────────────────────
function useDragReorder<T>(
  items: T[],
  setItems: React.Dispatch<React.SetStateAction<T[]>>,
  onReorder?: (newItems: T[]) => void
) {
  const dragIdx = useRef<number | null>(null);
  const overIdx = useRef<number | null>(null);

  const onDragStart = (i: number) => { dragIdx.current = i; };
  const setOverSlot = (slot: number) => { overIdx.current = slot; };
  const onDragEnd   = () => {
    const from = dragIdx.current;
    const slot = overIdx.current;
    dragIdx.current = overIdx.current = null;
    if (from === null || slot === null) return;
    if (slot === from || slot === from + 1) return;
    setItems((prev) => {
      const next = [...prev];
      const [moved] = next.splice(from, 1);
      const to = slot > from ? slot - 1 : slot;
      next.splice(to, 0, moved);
      onReorder?.(next);
      return next;
    });
  };

  return { onDragStart, setOverSlot, onDragEnd };
}

// ── main component ────────────────────────────────────────────────
export default function ExerciseEditor() {
  const [searchParams] = useSearchParams();
  const [exerciseId, setExerciseId]   = useState<string | null>(searchParams.get("id"));
  const [frames, setFrames]           = useState<Frame[]>([]);
  const [poses, setPoses]             = useState<PoseCommand[]>([]);
  const [status, setStatus]           = useState<StatusMsg>(null);
  const [uploading, setUploading]     = useState(false);
  const [fps, setFps]                 = useState(1);
  const [maxFrames, setMaxFrames]     = useState(8);
  const [loadingFrames, setLoadingFrames] = useState(false);
  const [running, setRunning]         = useState(false);
  const [insertingAt, setInsertingAt] = useState<number | null>(null);
  const [deletingAt, setDeletingAt]   = useState<number | null>(null);
  const [dragOver, setDragOver]       = useState<number | null>(null);
  const [voiceEditOpen, setVoiceEditOpen] = useState(false);
  const [exerciseName, setExerciseName] = useState("");
  const [calories, setCalories]         = useState<number | null>(null);
  const [caloriesLoading, setCaloriesLoading] = useState(false);
  const [description, setDescription]   = useState<string | null>(null);
  const [descLoading, setDescLoading]   = useState(false);
  const [editingName, setEditingName]   = useState(false);
  const [openVoiceLines, setOpenVoiceLines] = useState<number | null>(null)
  // maps frame idx → pose name for frames inserted from pose registry
  const [poseFrameMap, setPoseFrameMap] = useState<Record<number, string>>({});

  const fileInputRef = useRef<HTMLInputElement>(null);
  const drag = useDragReorder(frames, setFrames, (newFrames) => saveSequence(newFrames));

  // ── auto-load if ?id= param present ──────────────────────────
  useEffect(() => {
    const id = searchParams.get("id");
    if (id) loadFrames(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── load poses on mount ───────────────────────────────────────
  useEffect(() => {
    fetch(`${POSES_API}/commands`)
      .then((r) => r.json())
      .then((data) => {
        // Backend may return string[], { commands: string[] }, or a keyed object
        const names: string[] = Array.isArray(data)
          ? data
          : Array.isArray(data.commands)
          ? data.commands
          : Object.keys(data);
        setPoses(names.map((name) => ({ name })));
      })
      .catch(() => {/* poses not critical at startup */});
  }, []);

  const showStatus = (type: "success" | "error" | "info", text: string) => {
    setStatus({ type, text });
    if (type !== "error") setTimeout(() => setStatus(null), 4000);
  };

  // ── upload video ──────────────────────────────────────────────
  // POST /exercise/from_video  (multipart, field "video")
  // Returns the saved exercise config — extract id from it.
  const handleUpload = useCallback(async (file: File) => {
    if (!file.type.startsWith("video/")) {
      showStatus("error", "Prosím vyberte video súbor.");
      return;
    }
    setUploading(true);
    setStatus(null);
    setFrames([]);
    setExerciseId(null);

    try {
      const fd = new FormData();
      fd.append("video", file);
      fd.append("fps", String(fps));
      fd.append("max_frames", String(maxFrames));

      const res = await fetch(`${UPLOAD_API}/exercise/from_video`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) throw new Error(`Upload failed: HTTP ${res.status}`);
      const data = await res.json();
      const id = data.id ?? data.exercise_id ?? data.exerciseId ?? String(data);
      setExerciseId(id);
      showStatus("info", `Cvičenie vytvorené. Načítavam snímky…`);
      await loadFrames(id);
    } catch (err) {
      showStatus("error", err instanceof Error ? err.message : "Nahranie zlyhalo");
    } finally {
      setUploading(false);
    }
  }, [fps, maxFrames]);

  // ── load frames ───────────────────────────────────────────────
  // GET /exercise/<id>/frames  → plain array of frame objects
  // Each frame has: index (int), keypoints, nao_angles, joint_values
  const loadFrames = useCallback(async (id: string): Promise<Frame[]> => {
    setLoadingFrames(true);
    try {
      const res = await fetch(`${EDITOR_API}/exercise/${id}/frames`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      const NAO_JOINT_NAMES = [
        "LShoulderPitch","LShoulderRoll","LElbowRoll","LElbowYaw","LWristYaw",
        "RShoulderPitch","RShoulderRoll","RElbowRoll","RElbowYaw","RWristYaw",
        "LHipRoll","LHipPitch","LKneePitch","LAnklePitch","LAnkleRoll",
        "RHipRoll","RHipPitch","RKneePitch","RAnklePitch","RAnkleRoll",
        "HeadYaw","HeadPitch",
      ];

      const raw: any[] = Array.isArray(data) ? data : data.frames ?? [];
      const normalised: Frame[] = raw.map((f: any, i: number) => {
        const idx = f.idx ?? f.index ?? f.frame_index ?? i;
        let angles: Record<string, number> =
          f.joint_values ?? f.angles ?? f.joints ?? f.joint_angles ?? {};
        // fallback: build from nao_angles array if angles still empty
        if (Object.keys(angles).length === 0 && Array.isArray(f.nao_angles)) {
          angles = Object.fromEntries(
            (f.nao_angles as number[]).map((v, j) => [NAO_JOINT_NAMES[j] ?? `j${j}`, v])
          );
        }
        return {
          idx,
          angles,
          keypoints: f.keypoints,
          nao_angles: f.nao_angles,
          pose_name: f.pose_name ?? f.poseName ?? f.keypoints?.pose_name ?? undefined,
        };
      });

      setFrames(normalised);
      // Rebuild poseFrameMap from server data so stale entries for reused indices don't bleed through
      const freshPoseMap: Record<number, string> = {};
      for (const f of normalised) {
        if (f.pose_name) freshPoseMap[f.idx] = f.pose_name;
      }
      setPoseFrameMap(freshPoseMap);
      // fetch exercise name + existing calorie/description estimates
      fetch(`${EDITOR_API}/exercise/${id}`)
        .then((r) => r.json())
        .then((cfg) => {
          if (cfg.name) setExerciseName(cfg.name);
          if (cfg.calories != null) setCalories(cfg.calories);
          else estimateCalories(id, normalised);
          if (cfg.description) setDescription(cfg.description);
          else generateDescription(id, normalised);
        })
        .catch(() => {});
      showStatus("success", `Načítaných ${normalised.length} snímok.`);
      return normalised;
    } catch (err) {
      showStatus("error", err instanceof Error ? err.message : "Načítanie snímok zlyhalo");
      return [];
    } finally {
      setLoadingFrames(false);
    }
  }, []);

  // ── description generation via GPT ───────────────────────────
  const generateDescription = useCallback(async (id: string, frameList: Frame[]) => {
    if (!frameList.length || !LLM_AVAILABLE) return;
    setDescLoading(true);
    try {
      const jointRanges: Record<string, { min: number; max: number }> = {};
      for (const frame of frameList) {
        for (const [joint, val] of Object.entries(frame.angles)) {
          if (!jointRanges[joint]) jointRanges[joint] = { min: val, max: val };
          else {
            jointRanges[joint].min = Math.min(jointRanges[joint].min, val);
            jointRanges[joint].max = Math.max(jointRanges[joint].max, val);
          }
        }
      }
      const romSummary = Object.entries(jointRanges)
        .map(([j, { min, max }]) => `${j}: ${(max - min).toFixed(2)} rad`)
        .join(", ");

      const res = await fetch(`${LLM_API_BASE}/v1/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${LLM_API_KEY}` },
        body: JSON.stringify({
          model: LLM_MODEL,
          response_format: { type: "json_object" },
          messages: [
            {
              role: "system",
              content: `You are a fitness expert. Given NAO humanoid robot joint angle data for a physical exercise, write a short 1–2 sentence description in Slovak of what the exercise looks like and which body parts it involves. Return ONLY a JSON object: {"description": "<text>"}. Be concise and natural.`,
            },
            {
              role: "user",
              content: `Exercise has ${frameList.length} keyframes. Joint range-of-motion: ${romSummary}.`,
            },
          ],
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const parsed = JSON.parse(data.choices?.[0]?.message?.content ?? "{}");
      const desc = parsed.description?.trim();
      if (desc) {
        setDescription(desc);
        await fetch(`${EDITOR_API}/exercise/${id}/config`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ description: desc }),
        });
      }
    } catch {
      // best-effort
    } finally {
      setDescLoading(false);
    }
  }, []);

  // ── insert pose as a new frame ────────────────────────────────
  // POST /exercise/<id>/frame/from_pose
  // Body (JSON): { "pose_name": "<name>", "position": <seq index> }
  const insertPose = useCallback(async (position: number, poseName: string) => {
    if (!exerciseId) return;
    setInsertingAt(position);
    const oldIdxs = new Set(frames.map((f) => f.idx));
    try {
      const res = await fetch(`${EDITOR_API}/exercise/${exerciseId}/frame/from_pose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pose_name: poseName, position }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const newFrames = await loadFrames(exerciseId);
      const newFrame = newFrames.find((f) => !oldIdxs.has(f.idx));
      if (newFrame) {
        setPoseFrameMap((prev) => ({ ...prev, [newFrame.idx]: poseName }));
      }
      generateDescription(exerciseId, newFrames);
      showStatus("success", `Póza "${poseName}" vložená.`);
    } catch (err) {
      showStatus("error", err instanceof Error ? err.message : "Vloženie zlyhalo");
    } finally {
      setInsertingAt(null);
    }
  }, [exerciseId, frames, loadFrames, generateDescription]);

  // ── delete frame ──────────────────────────────────────────────
  // DELETE /exercise/<id>/frame/<idx>
  const deleteFrame = useCallback(async (frameIdx: number) => {
    if (!exerciseId) return;
    setDeletingAt(frameIdx);
    try {
      const res = await fetch(`${EDITOR_API}/exercise/${exerciseId}/frame/${frameIdx}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const remaining = frames.filter((f) => f.idx !== frameIdx);
      setFrames(remaining);
      generateDescription(exerciseId, remaining);
      showStatus("success", "Snímka odstránená.");
    } catch (err) {
      showStatus("error", err instanceof Error ? err.message : "Odstránenie zlyhalo");
    } finally {
      setDeletingAt(null);
    }
  }, [exerciseId, frames, generateDescription]);

  // ── save sequence ─────────────────────────────────────────────
  // PUT /exercise/<id>/sequence
  // Body (JSON): { "frame_sequence": [0, 2, 1, …] }   ← key is "frame_sequence"
  const saveSequence = useCallback(async (framesToSave?: Frame[]) => {
    if (!exerciseId) return;
    try {
      const frame_sequence = (framesToSave ?? frames).map((f) => f.idx);
      const res = await fetch(`${EDITOR_API}/exercise/${exerciseId}/sequence`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ frame_sequence }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showStatus("success", "Poradie uložené.");
    } catch (err) {
      showStatus("error", err instanceof Error ? err.message : "Uloženie zlyhalo");
    }
  }, [exerciseId, frames]);

  // ── rename exercise ───────────────────────────────────────────
  const renameExercise = useCallback(async (name: string) => {
    if (!exerciseId || !name.trim()) return;
    try {
      const res = await fetch(`${EDITOR_API}/exercise/${exerciseId}/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setExerciseName(name.trim());
    } catch {
      showStatus("error", "Premenovanie zlyhalo.");
    }
  }, [exerciseId]);

  // ── calorie estimation via GPT ────────────────────────────────
  const estimateCalories = useCallback(async (id: string, frameList: Frame[]) => {
    if (!frameList.length || !LLM_AVAILABLE) return;
    setCaloriesLoading(true);
    try {
      // summarise range-of-motion per joint across all frames
      const jointRanges: Record<string, { min: number; max: number }> = {};
      for (const frame of frameList) {
        for (const [joint, val] of Object.entries(frame.angles)) {
          if (!jointRanges[joint]) jointRanges[joint] = { min: val, max: val };
          else {
            jointRanges[joint].min = Math.min(jointRanges[joint].min, val);
            jointRanges[joint].max = Math.max(jointRanges[joint].max, val);
          }
        }
      }
      const romSummary = Object.entries(jointRanges)
        .map(([j, { min, max }]) => `${j}: ${(max - min).toFixed(2)} rad`)
        .join(", ");

      const res = await fetch(`${LLM_API_BASE}/v1/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${LLM_API_KEY}` },
        body: JSON.stringify({
          model: LLM_MODEL,
          response_format: { type: "json_object" },
          messages: [
            {
              role: "system",
              content: `You are a fitness expert. Given NAO humanoid robot joint angle data for a physical exercise, estimate the calories a person would burn performing this exercise once. Return ONLY a JSON object: {"calories": <number>}. Round to one decimal place.`,
            },
            {
              role: "user",
              content: `Exercise has ${frameList.length} keyframes. Joint range-of-motion: ${romSummary}.`,
            },
          ],
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const parsed = JSON.parse(data.choices?.[0]?.message?.content ?? "{}");
      const kcal = Number(parsed.calories);
      if (!isNaN(kcal) && kcal > 0) {
        setCalories(kcal);
        // persist to backend
        await fetch(`${EDITOR_API}/exercise/${id}/config`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ calories: kcal }),
        });
      }
    } catch {
      // estimation is best-effort, don't show error
    } finally {
      setCaloriesLoading(false);
    }
  }, []);

  // ── run on robot ──────────────────────────────────────────────
  // POST /exercise/<exercise_id>/run
  // Body (JSON, optional): { "repetitions": N }
  const runExercise = useCallback(async () => {
    if (!exerciseId) return;
    setRunning(true);
    try {
      const res = await fetch(`${UPLOAD_API}/exercise/${exerciseId}/run`, {
        method: "POST",
        // No body — repetitions defaults to the value stored in the exercise config.
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showStatus("success", "Cvičenie odoslané robotovi!");
    } catch (err) {
      showStatus("error", err instanceof Error ? err.message : "Spustenie zlyhalo");
    } finally {
      setRunning(false);
    }
  }, [exerciseId]);

  // ── drop zone ─────────────────────────────────────────────────
  const onDropZone = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  };

  // ── render ────────────────────────────────────────────────────
  return (
    <div className="w-full max-w-7xl mx-auto px-4 py-6 pb-24 space-y-6">

      {/* ── header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            Editor
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Nahrajte video, upravte snímky, spustite na robotovi.
          </p>
        </div>
        {exerciseId && (
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant={voiceEditOpen ? "default" : "outline"}
              onClick={() => setVoiceEditOpen((v) => !v)}
              disabled={!frames.length}
            >
              <Mic className="h-3.5 w-3.5 mr-1.5" />
              Hlasová úprava
            </Button>
            <Button
              size="sm"
              onClick={runExercise}
              disabled={running || !frames.length}
              className="text-primary-foreground"
            >
              {running
                ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                : <Play className="h-3.5 w-3.5 mr-1.5" />
              }
              Spustiť na robotovi
            </Button>
          </div>
        )}
      </div>

      {/* ── status alert ── */}
      {status && (
        <Alert
          variant={status.type === "error" ? "destructive" : "default"}
          className={
            status.type === "success" ? "border-green-500 bg-green-50 dark:bg-green-950/20" :
            status.type === "info"    ? "border-blue-500 bg-blue-50 dark:bg-blue-950/20" : ""
          }
        >
          {status.type === "error"
            ? <AlertCircle className="h-4 w-4" />
            : <CheckCircle className="h-4 w-4 text-green-600" />
          }
          <AlertDescription>{status.text}</AlertDescription>
        </Alert>
      )}

      {/* ── voice edit panel ── */}
      {voiceEditOpen && exerciseId && (
        <VoiceEditPanel
          poses={poses}
          frameCount={frames.length}
          onInsert={(position, poseName) => insertPose(position, poseName)}
          onClose={() => setVoiceEditOpen(false)}
        />
      )}

      {/* ── upload params ── */}
      {!exerciseId && (
        <div className="flex items-center gap-6">
          <label className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground whitespace-nowrap">Snímky za sekundu</span>
            <input
              type="number"
              min={1}
              max={30}
              value={fps}
              onChange={(e) => setFps(Math.max(1, Math.min(30, Number(e.target.value))))}
              className="w-16 h-7 text-sm text-center border border-border rounded-md bg-background text-foreground px-2"
            />
          </label>
          <label className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground whitespace-nowrap">Max snímok</span>
            <input
              type="number"
              min={1}
              max={200}
              value={maxFrames}
              onChange={(e) => setMaxFrames(Math.max(1, Math.min(200, Number(e.target.value))))}
              className="w-16 h-7 text-sm text-center border border-border rounded-md bg-background text-foreground px-2"
            />
          </label>
        </div>
      )}

      {/* ── upload zone (shown when no exercise loaded) ── */}
      {!exerciseId && (
        <Card
          className={[
            "border-2 border-dashed transition-colors duration-200 cursor-pointer",
            "hover:border-primary/50 hover:bg-muted/30",
            uploading ? "opacity-60 pointer-events-none" : "",
          ].join(" ")}
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDropZone}
          onClick={() => fileInputRef.current?.click()}
        >
          <div className="flex flex-col items-center justify-center gap-4 py-16 px-8 text-center">
            {uploading ? (
              <>
                <Loader2 className="h-10 w-10 text-primary animate-spin" />
                <p className="text-sm text-muted-foreground">Nahrávanie videa…</p>
              </>
            ) : (
              <>
                <div className="w-16 h-16 rounded-2xl bg-muted/50 flex items-center justify-center">
                  <Film className="h-8 w-8 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">Presuňte video sem</p>
                  <p className="text-xs text-muted-foreground mt-1">alebo kliknite pre výber</p>
                </div>
                <Badge variant="secondary" className="text-xs">MP4 · MOV · AVI · WEBM</Badge>
              </>
            )}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleUpload(f); }}
          />
        </Card>
      )}

      {/* ── upload new video button when exercise exists ── */}
      {exerciseId && (
        <div className="flex flex-col gap-2">
          {/* inline rename */}
        <div className="flex items-center gap-4">
          {editingName ? (
            <div className="flex items-center gap-1.5">
              <input
                autoFocus
                className="text-sm border border-border rounded px-2 py-0.5 bg-background text-foreground w-48"
                value={exerciseName}
                onChange={(e) => setExerciseName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") { renameExercise(exerciseName); setEditingName(false); }
                  if (e.key === "Escape") setEditingName(false);
                }}
              />
              <button onClick={() => { renameExercise(exerciseName); setEditingName(false); }}
                className="text-green-600 hover:text-green-700">
                <CheckCircle className="h-4 w-4" />
              </button>
              <button onClick={() => setEditingName(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <button
              className="flex items-center gap-1.5 text-sm text-foreground hover:text-primary transition-colors group"
              onClick={() => setEditingName(true)}
            >
              <span className="font-medium">{exerciseName || "Nepomenované cvičenie"}</span>
              <Pencil className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
            </button>
          )}

          {/* calorie estimate */}
          <div className="flex items-center gap-1.5">
            {caloriesLoading ? (
              <>
                <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                <span className="text-[11px] text-muted-foreground">Odhadovanie kalorií…</span>
              </>
            ) : calories != null ? (
              <>
                <span className="text-[11px] font-medium text-foreground">{calories} kcal</span>
                <span className="text-[10px] bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400 px-1.5 py-0.5 rounded-full">Odhad AI</span>
              </>
            ) : null}
          </div>

          <button
            className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors ml-auto"
            onClick={() => { setExerciseId(null); setFrames([]); setStatus(null); setExerciseName(""); setCalories(null); setDescription(null); }}
          >
            <Upload className="h-3.5 w-3.5" />
            Nahrať iné video
          </button>
        </div>

        {/* description */}
        {descLoading ? (
          <div className="flex items-center gap-1.5">
            <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
            <span className="text-[11px] text-muted-foreground">Generovanie popisu pomocou AI…</span>
          </div>
        ) : description ? (
          <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>
        ) : null}
      </div>
      )}

      {/* ── loading frames spinner ── */}
      {loadingFrames && (
        <Card className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 text-primary animate-spin" />
            <p className="text-sm text-muted-foreground">Načítavam snímky…</p>
          </div>
        </Card>
      )}

      {/* ── frame timeline ── */}
      {!loadingFrames && frames.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              {frames.length} Snímk{frames.length === 1 ? "a" : frames.length < 5 ? "y" : "ok"}
              <span className="ml-2 normal-case font-normal">— pretiahnite pre zmenu poradia</span>
            </p>
          </div>

          {/* horizontal scrollable frame strip */}
          <div className="overflow-x-auto md:overflow-x-auto overflow-y-auto pb-3">
            <div className="flex flex-col md:flex-row items-stretch gap-3 md:min-w-max">
              {frames.map((frame, i) => (
                <div key={`${frame.idx}-${i}`} className="flex items-stretch gap-3">
                  {/* insertion line before this card */}
                  {dragOver === i && (
                    <div className="md:w-0.5 md:self-stretch h-0.5 md:h-auto w-full bg-primary rounded-full shrink-0" />
                  )}
                  <FrameCard
                    frame={{ ...frame, pose_name: poseFrameMap[frame.idx] ?? frame.pose_name }}
                    position={i}
                    exerciseId={exerciseId!}
                    poses={poses}
                    onInsertBefore={(pose) => insertPose(i, pose)}
                    onInsertAfter={(pose) => insertPose(i + 1, pose)}
                    onDelete={() => deleteFrame(frame.idx)}
                    inserting={insertingAt !== null}
                    deleting={deletingAt === frame.idx}
                    isDragOver={false}
                    showStatus={showStatus}
                    draggable
                    openVoiceLines={openVoiceLines}
                    setOpenVoiceLines={setOpenVoiceLines}
                    onDragStart={() => drag.onDragStart(i)}
                    onDragEnter={() => {}}
                    onDragEnd={() => { drag.onDragEnd(); setDragOver(null); }}
                    onDragOver={(e: React.DragEvent) => {
                      e.preventDefault();
                      const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
                      const slot = e.clientX < rect.left + rect.width / 2 ? i : i + 1;
                      drag.setOverSlot(slot);
                      setDragOver(slot);
                    }}

                  />
                </div>
              ))}
              {/* insertion line at the end */}
              {dragOver === frames.length && (
                <div className="w-0.5 self-stretch bg-primary rounded-full flex-shrink-0" />
              )}
            </div>
          </div>

        </div>
      )}

      {/* ── empty state after load ── */}
      {!loadingFrames && exerciseId && frames.length === 0 && (
        <Card className="flex flex-col items-center justify-center py-16 gap-3">
          <Film className="h-8 w-8 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">Nenašli sa žiadne snímky.</p>
          <Button variant="outline" size="sm" onClick={() => loadFrames(exerciseId)}>
            Skúsiť znova
          </Button>
        </Card>
      )}
    </div>
  );
}

// ── AnglesTooltip ─────────────────────────────────────────────────
function AnglesTooltip({ angles }: { angles: Record<string, number> }) {
  const [open, setOpen] = useState(false);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = () => {
    if (hideTimer.current) clearTimeout(hideTimer.current);
    setOpen(true);
  };
  const hide = () => {
    hideTimer.current = setTimeout(() => setOpen(false), 120);
  };

  const count = Object.keys(angles).length;

  return (
    <div className="px-3 pb-1 relative">
      <p
        className="text-[10px] text-muted-foreground cursor-default"
        onMouseEnter={count > 0 ? show : undefined}
        onMouseLeave={count > 0 ? hide : undefined}
      >
        {count > 0 ? `Uhly (${count})` : <span className="italic">žiadne dáta uhlov</span>}
      </p>
      {open && count > 0 && (
        <div
          className="absolute bottom-full left-0 w-52 z-50 rounded-lg border border-border bg-popover shadow-lg px-2 py-1.5 max-h-52 overflow-y-auto"
          onMouseEnter={show}
          onMouseLeave={hide}
        >
          {Object.entries(angles).map(([k, v]) => (
            <div key={k} className="flex justify-between font-mono text-[9px] text-muted-foreground py-px">
              <span>{k}</span>
              <span>{typeof v === "number" ? v.toFixed(3) : v}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── FrameCard sub-component ───────────────────────────────────────
type FrameCardProps = {
  frame: Frame;
  position: number;
  exerciseId: string;
  poses: PoseCommand[];
  onInsertBefore: (pose: string) => void;
  onInsertAfter: (pose: string) => void;
  onDelete: () => void;
  inserting: boolean;
  deleting: boolean;
  isDragOver: boolean;
  draggable: boolean;
  onDragStart: () => void;
  onDragEnter: () => void;
  onDragEnd: () => void;
  onDragOver: (e: React.DragEvent) => void;
};

function FrameCard({
  frame,
  position,
  exerciseId,
  poses,
  onInsertBefore,
  onInsertAfter,
  onDelete,
  inserting,
  deleting,
  showStatus,
  isDragOver,
  openVoiceLines, 
  setOpenVoiceLines,
  ...dragProps
}: FrameCardProps) {
  const imageUrl = `${EDITOR_API}/exercise/${exerciseId}/frame/${frame.idx}/image`;
  const poseImageUrl = frame.pose_name ? `${POSES_API}/pose/${frame.pose_name}/image` : null;
  const [imgError, setImgError] = useState(false);
  const [poseImgError, setPoseImgError] = useState(false);
  const [beforeVal, setBeforeVal] = useState("");
  const [afterVal, setAfterVal]   = useState("");
  const [toggleText, setTextToggle] = useState(false);
  const [naoSaying, setNaoSaying] = useState(false);
  const noExtractedText = "Nothing so far";
  const textAreaRef = useRef<any>(null);
  const [overallRecordedMessage, onOverallRecordedMessageChange] = useState({"extractedText": noExtractedText});
  const [savingAt, setSavingVoiceLinesAt]  = useState<number | null>(null);
  const [speechLanguage, setSpeechLanguage] = useState<string>("English");
  const [speechSpeed, setSpeechSpeed] = useState<number>(100);
  
  const audioRecorderRef = useRef(null);
  const aggregatedVoiceLinesRef = useRef<HTMLTextAreaElement>(null);
  let [configLoaded, setConfigLoaded] = useState(false);
  const [voiceLinesLoaded, setVoiceLinesLoaded] = useState(false);

  
  const imgEl = !imgError ? (
    <img src={imageUrl} alt={`Frame ${frame.idx}`} className="w-full h-full object-cover rounded-lg bg-muted" onError={() => setImgError(true)} />
  ) : poseImageUrl && !poseImgError ? (
    <img src={poseImageUrl} alt={frame.pose_name} className="w-full h-full object-cover rounded-lg bg-muted" onError={() => setPoseImgError(true)} />
  ) : (
    <div className="w-full h-full rounded-lg bg-muted flex items-center justify-center">
      <Film className="h-5 w-5 text-muted-foreground/40" />
    </div>
  );

  const extractText = (overallMessages: any) => {
    let resultingText = "";
    console.log(overallMessages);
    if (overallMessages["extractedText"] !== undefined && overallMessages["extractedText"] !== "Nothing so far") {
      console.log(overallMessages["extractedText"]);
      return overallMessages["extractedText"];
    }
    if (overallMessages["voice_lines_configs"] !== undefined) {
      for (const [key, value] of Object.entries(overallMessages["voice_lines_configs"])) {
          if (value["translation"] !== undefined) { 
              resultingText = resultingText + " " + value["translation"];
          }
      }
    }
    
    return resultingText;
  }


  useEffect(() => {
    async function loadVoiceLines(overallRecordedMessage) {
      if (!overallRecordedMessage || !configLoaded) {
       setConfigLoaded(true);
        try {
          fetch(`${EDITOR_API}/voiceLines/config/exercise/${exerciseId}/frame/${frame.idx}`, {
            method: "GET",
          }).then((response) => {
            if (response.ok) {
              return response.json();
            }
            throw new Error("Message not in JSON");
          })
          .then((data) => {
            const extractededText = extractText(data);
            if  ( extractededText !== "") {
                /*for (const [key, value] of Object.entries(data["voice_lines_configs"])) {
                  if (overallRecordedMessage["voice_lines_configs"] === undefined) {
                      overallRecordedMessage["voice_lines_configs"] = {};
                  }
                  overallRecordedMessage["voice_lines_configs"][key] = value;
                }*/
                console.log("LODED.........................................");
                console.log(data);
                if (data["lang"] !== undefined) {
                  overallRecordedMessage["lang"] = data["lang"]; 
                  setSpeechLanguage(data["lang"]);
                }
                if (data["speed"] !== undefined) {
                  overallRecordedMessage["speed"] = data["speed"]; 
                   setSpeechSpeed(data["speed"]);
                }

                overallRecordedMessage["extractedText"] = extractededText;
                aggregatedVoiceLinesRef.current.value = overallRecordedMessage["extractedText"];
                onOverallRecordedMessageChange(overallRecordedMessage);
            } 
          })
          .catch((error) => {
            console.log(error);
          });
        } catch(e) {
          console.log(e);
        }
      }
    }

    loadVoiceLines(overallRecordedMessage);
  }, [overallRecordedMessage]);

  useEffect(()=>{
    async function fetchAllVoiceLines() {
    if (toggleText && !voiceLinesLoaded) {
      setVoiceLinesLoaded(true);
      let resultingText = "";
      if (overallRecordedMessage["voice_lines_configs"] !== undefined ) {
        for (const [key, value] of Object.entries(overallRecordedMessage["voice_lines_configs"])) {
          try {
            fetch(`${EDITOR_API}/voiceLines/sound/exercise/${exerciseId}/frame/${frame.idx}/${value["fileName"]}`, {
              method: "GET",
            }).then((response) => {
              if (response.ok) {
                return response.json();
              }
              throw new Error("Message not in JSON");
            })
            .then((data) => {
              const audioFormat = data["audioFormat"];
              const audioInBase64 = data["sound"];
              if (audioFormat === "webm") {
                audioRecorderRef.current.createCustomAudioPlayerFromBase64(audioInBase64, value["translation"]);
              }
            })
            .catch((error) => {
              console.log(error);
            });
          } catch(e) {
            console.log(e);
          }
        }
      }
      }
    }
    
    fetchAllVoiceLines(); 
  },[toggleText]);

  const saveAudioFile = async (audioInBase64, fileNameWithFormat) => {
    const res = await fetch(`${EDITOR_API}/voiceLines/sound/exercise/${exerciseId}/frame/${frame.idx}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          "sound": audioInBase64,
          "file_name": fileNameWithFormat
        })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      //showStatus("success", "Subot s hláškami " + fileNameWithFormat + " uložené.");
  };

  const onSavingVoiceLines = async (exerciseId: number, frameIdx: number, overallRecordedMessage: any) => {
    setSavingVoiceLinesAt(frameIdx);
    overallRecordedMessage["lang"] = speechLanguage;
    overallRecordedMessage["speed"] = speechSpeed;
    try {
      const res = await fetch(`${EDITOR_API}/voiceLines/config/exercise/${exerciseId}/frame/${frameIdx}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          "voice_lines": overallRecordedMessage
        })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showStatus("success", "Hlášky uložené.");
    } catch (err) {
      showStatus("error", err instanceof Error ? err.message : "Uloženie hlášok zlyhalo");
    } finally {
      setSavingVoiceLinesAt(null);
    }
  }


    const onRobotSay = async (textConfigToBeSaid) => {
      setNaoSaying(true);
      console.log(textConfigToBeSaid);
      try {
        const res = await fetch(`${ROBOT_API}/voiceLines/applyVoiceLine`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            "voice_lines": textConfigToBeSaid
          })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        showStatus("success", "Robot povedal.");
      } catch (err) {
        showStatus("error", err instanceof Error ? err.message : "Uloženie hlášok zlyhalo");
      } finally {
        setNaoSaying(null);
      }
    }


    
  const testVoiceLines = async () => {
    if (audioRecorderRef.current !== null) {
      console.log(aggregatedVoiceLinesRef.current);
      let textFromTextArea = aggregatedVoiceLinesRef.current.value;
      
      console.log(textFromTextArea);
      if (textFromTextArea !== "Nothing so far") {
          const textConfigToBeSaid = {
            "voice_lines_configs": {"entire": {"translation": textFromTextArea}},
            "lang": speechLanguage,
            "speed": speechSpeed
          }
          onRobotSay(textConfigToBeSaid);
          return;
      }

      let textConfigToBeSaid = audioRecorderRef.current.getTextConfigFromVoiceLinesToBeSaidByRobot();
      if (Object.keys(textConfigToBeSaid["voice_lines_configs"]).length === 0 && overallRecordedMessage["extractedText"] !== noExtractedText) {
        textConfigToBeSaid["voice_lines_configs"] = overallRecordedMessage["voice_lines_configs"];
      }
      textConfigToBeSaid["lang"] = speechLanguage;
      textConfigToBeSaid["speed"] = speechSpeed;
      onRobotSay(textConfigToBeSaid);
    } else {
      if (aggregatedVoiceLinesRef === null) { 
        throw new Exception("HTML Textarea not initialized.");
        return;
      }
      const textToBeSaidByRobot = aggregatedVoiceLinesRef.current.value;
      onRobotSay(textConfigToBeSaid);
    }
  }


  return (
    <div
      {...dragProps}
      className={[
        "w-full md:w-52 md:shrink-0 rounded-xl border bg-card text-card-foreground shadow-sm",
        "transition-all duration-150 cursor-grab active:cursor-grabbing",
        deleting ? "opacity-40 pointer-events-none" : "",
      ].join(" ")}
    >
      {/* ── mobile: compact horizontal row ── */}
      <div className="flex md:hidden items-center gap-3 px-3 py-2">
        {/* thumbnail */}
        <div className="w-14 h-14 shrink-0 rounded-lg overflow-hidden bg-muted">
          {imgEl}
        </div>
        {/* index + drag handle */}
        <div className="flex flex-col gap-1 flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <span className="bg-muted text-muted-foreground text-[10px] font-mono px-1.5 py-0.5 rounded">
              #{position + 1}
            </span>
            <GripVertical className="h-4 w-4 text-muted-foreground/40" />
          </div>
          {/* insert selects inline */}
          <div className="flex gap-1.5">
            <select
              className="flex-1 h-6 rounded border border-gray-300 bg-white text-gray-800 text-[10px] px-1 disabled:opacity-50"
              value=""
              onChange={(e) => { if (e.target.value) { onInsertBefore(e.target.value); e.target.value = ""; } }}
              disabled={inserting}
            >
              <option value="" disabled>← Pred</option>
              {poses.map((p) => <option key={p.name} value={p.name}>{POSE_DISPLAY_SK[p.name] ?? p.name}</option>)}
            </select>
            <select
              className="flex-1 h-6 rounded border border-gray-300 bg-white text-gray-800 text-[10px] px-1 disabled:opacity-50"
              value=""
              onChange={(e) => { if (e.target.value) { onInsertAfter(e.target.value); e.target.value = ""; } }}
              disabled={inserting}
            >
              <option value="" disabled>Za →</option>
              {poses.map((p) => <option key={p.name} value={p.name}>{POSE_DISPLAY_SK[p.name] ?? p.name}</option>)}
            </select>
            <button
              onClick={onDelete}
              disabled={deleting}
              className="text-gray-400 hover:text-red-500 transition-colors px-1"
            >
              {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>
      </div>

      {/* ── desktop: vertical card ── */}
      <div className="hidden md:flex flex-col h-full">
        {/* header */}
        <div className="flex items-center justify-between px-3 pt-3 pb-2">
          <span className="bg-muted text-muted-foreground text-[10px] font-mono px-1.5 py-0.5 rounded">
            #{position + 1}
          </span>
          <GripVertical className="h-4 w-4 text-muted-foreground/40" />
        </div>

        {/* image */}
        <div className="px-3 pb-2 flex-1">
          {!imgError ? (
            <img src={imageUrl} alt={`Frame ${frame.idx}`} className="w-full h-auto rounded-lg bg-muted" onError={() => setImgError(true)} />
          ) : poseImageUrl && !poseImgError ? (
            <img src={poseImageUrl} alt={frame.pose_name} className="w-full h-auto rounded-lg bg-muted" onError={() => setPoseImgError(true)} />
          ) : (
            <div className="w-full h-32 rounded-lg bg-muted flex items-center justify-center">
              <Film className="h-6 w-6 text-muted-foreground/40" />
            </div>
          )}
        </div>

        {/* bottom */}
        <div className="mt-auto">
          <AnglesTooltip angles={frame.angles} />
          <div className="px-3 pt-1 pb-1">
            <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">Vložiť pózu</p>
          </div>
          <div className="px-3 pb-3 flex gap-1.5">
            <label className="flex-1 flex flex-col gap-0.5">
              <span className="text-[10px] text-gray-500 flex items-center gap-0.5">
                <ChevronLeft className="h-3 w-3" /> Pred
              </span>
              <select
                className="w-full h-7 rounded-md border border-gray-300 bg-white text-gray-800 text-xs px-1.5 disabled:opacity-50"
                value=""
                onChange={(e) => { if (e.target.value) { onInsertBefore(e.target.value); e.target.value = ""; } }}
                disabled={inserting}
              >
                <option value="" disabled>Póza…</option>
                {poses.map((p) => <option key={p.name} value={p.name}>{POSE_DISPLAY_SK[p.name] ?? p.name}</option>)}
              </select>
            </label>
            <label className="flex-1 flex flex-col gap-0.5">
              <span className="text-[10px] text-gray-500 flex items-center gap-0.5 justify-end">
                Za <ChevronRight className="h-3 w-3" />
              </span>
              <select
                className="w-full h-7 rounded-md border border-gray-300 bg-white text-gray-800 text-xs px-1.5 disabled:opacity-50"
                value=""
                onChange={(e) => { if (e.target.value) { onInsertAfter(e.target.value); e.target.value = ""; } }}
                disabled={inserting}
              >
                <option value="" disabled>Póza…</option>
                {poses.map((p) => <option key={p.name} value={p.name}>{POSE_DISPLAY_SK[p.name] ?? p.name}</option>)}
              </select>
            </label>
          </div>
          <div>
            <div>
              <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide" style={{ flex: "0 0 calc(100% - 70px)", marginLeft: "10px" }}>What NAO says</p>
              <textarea ref={aggregatedVoiceLinesRef} style={{width: "100%", height: "100px", border: "1px solid black", borderRadius: "25px",
                 padding: "30px 30px 30px 30px"}} name="textFromVideo" 
                 onChange={(e) => {overallRecordedMessage["extractedText"] = e.target.value; onOverallRecordedMessageChange(overallRecordedMessage); }}>
                  {overallRecordedMessage["extractedText"]}
              </textarea>
              <div className="flex items-center gap-2" style={{"margin": "10px 10px 10px 10px"}}>
                <button
                  onClick={() => onSavingVoiceLines(exerciseId, frame.idx, overallRecordedMessage)}
                  disabled={savingAt === frame.idx}
                  className="w-full flex items-center justify-center gap-1.5 text-[11px] text-gray-400 hover:text-red-500 transition-colors py-1 rounded-md hover:bg-red-50"
                  aria-label="Uložiť hlášky"
                >
                {savingAt === frame.idx
                  ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  : <Save className="h-3.5 w-3.5" />
                }
                Uložiť hlášky
              </button>
              <Button
                size="sm"
                onClick={testVoiceLines}
                disabled={naoSaying}
                className="text-primary-foreground"
              >
                {naoSaying
                  ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                  : <Play className="h-3.5 w-3.5 mr-1.5" />
                }
                Povedz
              </Button>
            </div>
          </div>
            <div style={{display: "flex"}}>
              <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide" style={{ flex: "0 0 calc(100% - 70px)", marginLeft: "10px" }}>Record and speech summary</p>
              
              <Switch.Root onCheckedChange={(e) => {
                
                 setTextToggle(e);
                 if (!toggleText) { 
                    setOpenVoiceLines(frame.idx); 
                 } else { 
                    setOpenVoiceLines(null); 
                 }   
              }} style={{width: "50px", marginRight: "10px"}} className="SwitchRoot">
                  <Switch.Thumb className="SwitchThumb" />
              </Switch.Root>
            </div>
          </div>
          <div style={{display: (openVoiceLines === frame.idx && toggleText)? "block": "none", position: "relative"}}>
              <div style={{position: "absolute"}}>
                <AudioRecorderComponent ref={audioRecorderRef} speechSpeed={speechSpeed} setSpeechSpeed={setSpeechSpeed} speechLanguage={speechLanguage} setSpeechLanguage={setSpeechLanguage} saveAudioFile={saveAudioFile} overallRecordedMessage={overallRecordedMessage} onOverallRecordedMessageChange={onOverallRecordedMessageChange} aggregatedVoiceLinesRef={aggregatedVoiceLinesRef}/>
              </div>
          </div>
          <div className="px-3 pb-3">
            <button
              onClick={onDelete}
              disabled={deleting}
              className="w-full flex items-center justify-center gap-1.5 text-[11px] text-gray-400 hover:text-red-500 transition-colors py-1 rounded-md hover:bg-red-50"
              aria-label="Odstrániť snímku"
            >
            {deleting
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <Trash2 className="h-3.5 w-3.5" />
            }
            Odstrániť
          </button>
        </div>
        </div>{/* end bottom */}
      </div>{/* end desktop card */}
    </div>
  );
}

// ── local keyword fallback for VoiceEditPanel ─────────────────────
const POSE_ALIASES: [string, string][] = [
  ["drep", "crouch"],
  ["úklon", "bow"], ["uklon", "bow"],
  ["zamávaj", "wave"], ["zamavaj", "wave"], ["zamávajte", "wave"],
  ["stoj", "stand"],
  ["sed", "sit"], ["sadni", "sit"],
  ["ruky hore", "hands_up"],
  ["t-póza", "t_pose"], ["t póza", "t_pose"], ["tpóza", "t_pose"], ["t poza", "t_pose"],
  ["ukáž vpravo", "point_right"], ["ukaz vpravo", "point_right"],
  ["ukáž vľavo", "point_left"], ["ukaz vlavo", "point_left"],
  ["crouch", "crouch"], ["bow", "bow"], ["wave", "wave"], ["stand", "stand"],
  ["sit", "sit"], ["hands up", "hands_up"], ["t pose", "t_pose"], ["t-pose", "t_pose"],
  ["point right", "point_right"], ["point left", "point_left"],
];

const NUM_WORDS: Record<string, number> = {
  "jeden": 1, "jedna": 1, "jedno": 1, "one": 1,
  "dva": 2, "dve": 2, "two": 2,
  "tri": 3, "three": 3,
  "štyri": 4, "four": 4,
  "päť": 5, "five": 5,
  "šesť": 6, "six": 6,
  "sedem": 7, "seven": 7,
  "osem": 8, "eight": 8,
  "deväť": 9, "nine": 9,
  "desať": 10, "ten": 10,
};

function parseCommandLocally(transcript: string, poses: PoseCommand[], frameCount: number): ParsedCommand | null {
  const lower = transcript.toLowerCase();
  const side: "before" | "after" = /\bpred\b|before/.test(lower) ? "before" : "after";

  let frame: number | null = null;
  const digitMatch = lower.match(/\d+/);
  if (digitMatch) frame = parseInt(digitMatch[0]);
  else for (const [word, num] of Object.entries(NUM_WORDS)) {
    if (lower.includes(word)) { frame = num; break; }
  }
  if (!frame || frame < 1 || frame > frameCount) return null;

  let pose: string | null = null;
  for (const [alias, key] of POSE_ALIASES) {
    if (lower.includes(alias) && poses.some(p => p.name === key)) { pose = key; break; }
  }

  return { pose, frame, side };
}

// ── VoiceEditPanel ────────────────────────────────────────────────
type VoiceEditPanelProps = {
  poses: PoseCommand[];
  frameCount: number;
  onInsert: (position: number, poseName: string) => void;
  onClose: () => void;
};

type ParsedCommand = { pose: string | null; frame: number; side: "before" | "after" };

function VoiceEditPanel({ poses, frameCount, onInsert, onClose }: VoiceEditPanelProps) {
  const [listening, setListening]   = useState(false);
  const [transcript, setTranscript] = useState("");
  const [phase, setPhase]           = useState<"idle" | "parsing" | "pick_pose" | "confirm" | "error">("idle");
  const [parsed, setParsed]         = useState<ParsedCommand | null>(null);
  const [pickedPose, setPickedPose] = useState("");
  const [errorMsg, setErrorMsg]     = useState("");
  const recRef = useRef<any>(null);

  const startListening = () => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) { setErrorMsg("Rozpoznávanie hlasu nie je podporované — použite Chrome alebo Edge."); setPhase("error"); return; }
    const rec = new SR();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = "sk-SK";
    rec.onstart  = () => setListening(true);
    rec.onend    = () => setListening(false);
    rec.onerror  = () => { setListening(false); };
    rec.onresult = (e: any) => {
      let text = "";
      for (let i = e.resultIndex; i < e.results.length; i++)
        text += e.results[i][0].transcript;
      setTranscript(text);
    };
    recRef.current = rec;
    rec.start();
  };

  const stopListening = () => recRef.current?.stop();

  const applyParsed = (result: ParsedCommand) => {
    setParsed(result);
    if (!result.pose) { setPickedPose(""); setPhase("pick_pose"); }
    else setPhase("confirm");
  };

  const parseWithLLM = async () => {
    if (!transcript.trim()) return;
    setPhase("parsing");

    if (!LLM_AVAILABLE) {
      const result = parseCommandLocally(transcript, poses, frameCount);
      if (result) applyParsed(result);
      else { setErrorMsg("Nepodarilo sa rozpoznať príkaz. Skúste znova."); setPhase("error"); }
      return;
    }

    const poseList = poses.map((p) => p.name).join(", ");
    try {
      const res = await fetch(`${LLM_API_BASE}/v1/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${LLM_API_KEY}` },
        body: JSON.stringify({
          model: LLM_MODEL,
          response_format: { type: "json_object" },
          messages: [
            {
              role: "system",
              content: `You are a voice command parser for an exercise frame editor. The user speaks Slovak (or mixed Slovak/English). They have ${frameCount} frames numbered 1 to ${frameCount}.

Valid pose keys: [${poseList}].
Slovak→key hints: drep→crouch, úklon→bow, zamávaj/zamávajte→wave, stoj→stand, sed/sadni→sit, ruky hore→hands_up, t póza/t-póza/tpóza/tipos/depóza/te póza/tpose→t_pose, ukáž vpravo→point_right, ukáž vľavo→point_left.
Slovak side words: pred/pred snímkou→"before", po/za/po snímke→"after".

Return ONLY a JSON object with these fields:
- "pose": one of the valid keys above, or null if you cannot identify the pose
- "frame": integer 1–${frameCount}, or null if not mentioned
- "side": "before" or "after", or null if not mentioned

No other text, only JSON.`,
            },
            { role: "user", content: transcript },
          ],
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const cmd = JSON.parse(data.choices?.[0]?.message?.content ?? "{}");
      if (!cmd.frame || !cmd.side) throw new Error("no frame/side");
      const poseKey = cmd.pose && poses.some((p) => p.name === cmd.pose) ? cmd.pose : null;
      applyParsed({ pose: poseKey, frame: Number(cmd.frame), side: cmd.side === "before" ? "before" : "after" });
    } catch {
      const result = parseCommandLocally(transcript, poses, frameCount);
      if (result) applyParsed(result);
      else { setErrorMsg("Nepodarilo sa rozpoznať príkaz. Skúste znova."); setPhase("error"); }
    }
  };

  const confirm = (poseOverride?: string) => {
    if (!parsed) return;
    const pose = poseOverride ?? parsed.pose;
    if (!pose) return;
    const position = parsed.side === "after" ? parsed.frame : parsed.frame - 1;
    onInsert(position, pose);
    onClose();
  };

  const reset = () => { setPhase("idle"); setParsed(null); setTranscript(""); setPickedPose(""); };

  return (
    <div className="rounded-xl border border-border bg-card shadow-sm p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium text-foreground">Hlasová úprava</p>
          {LLM_AVAILABLE
            ? <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">AI aktívna</span>
            : <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500 font-medium">Bez AI</span>
          }
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
          <X className="h-4 w-4" />
        </button>
      </div>

      <p className="text-xs text-gray-500">
        {LLM_AVAILABLE
          ? <>Povedzte napr. <span className="italic">"vlož drep za snímku 3"</span> — AI rozpozná aj skomolené slová.</>
          : <>Povedzte napr. <span className="italic">"vlož drep za snímku 3"</span> — detekcia kľúčových slov (bez AI).</>
        }
      </p>

      {/* mic button */}
      <div className="flex items-center gap-3">
        <button
          onClick={listening ? stopListening : startListening}
          className={[
            "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors",
            listening
              ? "bg-red-500 text-white hover:bg-red-600"
              : "bg-gray-100 text-gray-700 hover:bg-gray-200",
          ].join(" ")}
        >
          {listening
            ? <><MicOff className="h-4 w-4" /> Zastaviť</>
            : <><Mic className="h-4 w-4" /> Hovoriť</>
          }
        </button>
        {transcript && (
          <p className="text-sm text-foreground flex-1 italic">"{transcript}"</p>
        )}
      </div>

      {/* parse button */}
      {transcript && phase === "idle" && (
        <Button size="sm" className="w-full" onClick={parseWithLLM} disabled={listening}>
          Rozpoznať príkaz
        </Button>
      )}

      {/* parsing spinner */}
      {phase === "parsing" && (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Loader2 className="h-4 w-4 animate-spin" /> Interpretuje sa…
        </div>
      )}

      {/* pose picker — frame+side known, pose unclear */}
      {phase === "pick_pose" && parsed && (
        <div className="space-y-2">
          <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-sm text-amber-800">
            Snímka <strong>{parsed.frame}</strong>, smer <strong>{parsed.side === "before" ? "pred" : "za"}</strong> — vyberte pózu:
          </div>
          <select
            className="w-full h-9 rounded-md border border-border bg-background text-foreground text-sm px-2"
            value={pickedPose}
            onChange={(e) => setPickedPose(e.target.value)}
          >
            <option value="" disabled>Póza…</option>
            {poses.map((p) => (
              <option key={p.name} value={p.name}>{POSE_DISPLAY_SK[p.name] ?? p.name}</option>
            ))}
          </select>
          <div className="flex gap-2">
            <Button size="sm" className="flex-1" disabled={!pickedPose} onClick={() => confirm(pickedPose)}>Potvrdiť</Button>
            <Button size="sm" variant="outline" className="flex-1" onClick={reset}>Skúsiť znova</Button>
          </div>
        </div>
      )}

      {/* confirm */}
      {phase === "confirm" && parsed?.pose && (
        <div className="space-y-2">
          <div className="rounded-lg bg-green-50 border border-green-200 px-3 py-2 text-sm text-green-800">
            Vložiť <strong>{POSE_DISPLAY_SK[parsed.pose] ?? parsed.pose}</strong> {parsed.side === "before" ? "pred" : "za"} snímku <strong>{parsed.frame}</strong>
          </div>
          <div className="flex gap-2">
            <Button size="sm" className="flex-1" onClick={() => confirm()}>Potvrdiť</Button>
            <Button size="sm" variant="outline" className="flex-1" onClick={reset}>Skúsiť znova</Button>
          </div>
        </div>
      )}

      {/* error */}
      {phase === "error" && (
        <div className="space-y-2">
          <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
            {errorMsg}
          </div>
          <Button size="sm" variant="outline" className="w-full" onClick={reset}>
            Skúsiť znova
          </Button>
        </div>
      )}
    </div>
  );
}