import { useState, useRef, useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { NativeSelect } from "@/components/ui/native-select";
import { DropdownMenu } from "radix-ui";
import { VideoTrimmer } from "@/components/ui/videoTrimmer";
import { FileDropzone } from "@/components/ui/fileDropzone";
import { SelectedFileCard } from "@/components/ui/selectedFileCard";
import { ExerciseNameInput } from "@/components/exercise/exerciseNameInput";
import { appendVideoRange, type VideoRange } from "@/lib/videoRange";
import { useSelectedFile } from "@/hooks/useSelectedFile";
import { useStatus, type StatusType } from "@/hooks/useStatus";
import { StatusAlert } from "@/components/ui/statusAlert";
import { PageHeader } from "@/components/layout/pageHeader";
import { poseLabel } from "@/lib/poses";
import { pluralSk } from "@/lib/plural";
import { failureText } from "@/lib/errors";
import { MicButton } from "@/components/ui/micButton";
import { AiBadge } from "@/components/ui/aiBadge";
import { TranscriptBlock } from "@/components/ui/transcriptBlock";
import { LLM_API_BASE, LLM_API_KEY, LLM_MODEL, LLM_AVAILABLE } from "@/lib/llm";
import {
  NO_VOICE_TEXT,
  hasVoiceText,
  voiceTextFromConfig,
  blobToBase64,
  SPEECH_LANGUAGES,
  SPEECH_SPEEDS,
  DEFAULT_SPEECH_LANGUAGE,
  DEFAULT_SPEECH_SPEED,
  type VoiceLinesConfig,
} from "@/lib/voiceLines";
import {
  Loader2,
  Upload,
  Play,
  Trash2,
  GripVertical,
  Film,
  ChevronLeft,
  ChevronRight,
  Mic,
  X,
  MoreHorizontal,
  Square,
  Check,
  Languages,
  Gauge,
  Flame
} from "lucide-react";


// ── API config ────────────────────────────────────────────────────
const UPLOAD_API = "http://localhost:7000"; //empty for reverse proxy nginx
const EDITOR_API = "http://localhost:7001";
const POSES_API  = "http://localhost:8000";
const ROBOT_API  = "http://localhost:5000";
const TO_TEXT_API = "http://localhost:9901";

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
  const { status, show: showStatus, clear: clearStatus } = useStatus();
  const [uploading, setUploading]     = useState(false);
  const [fps, setFps]                 = useState(1);
  const [maxFrames, setMaxFrames]     = useState(8);
  // video waiting for range choice before upload
  const pending = useSelectedFile();
  const [videoRange, setVideoRange]   = useState<VideoRange | null>(null);
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
  // maps frame idx → pose name for frames inserted from pose registry
  const [poseFrameMap, setPoseFrameMap] = useState<Record<number, string>>({});

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


  // ── select video ──────────────────────────────────────────────
  const selectVideo = (file: File) => {
    if (!file.type.startsWith("video/")) {
      showStatus("error", "Prosím vyberte video súbor.");
      return;
    }
    clearStatus();
    setVideoRange(null);
    pending.select(file);
  };

  const clearPendingVideo = () => {
    pending.clear();
    setVideoRange(null);
  };

  // back to upload zone for new video
  const resetEditor = () => {
    clearPendingVideo();
    setExerciseId(null);
    setFrames([]);
    clearStatus();
    setExerciseName("");
    setCalories(null);
    setDescription(null);
  };

  // ── upload video ──────────────────────────────────────────────
  // POST /exercise/from_video  (multipart, field "video", optional "start"/"end" in seconds)
  // Returns the saved exercise config — extract id from it.
  const handleUpload = useCallback(async (file: File, range: VideoRange | null) => {
    setUploading(true);
    clearStatus();
    setFrames([]);
    setExerciseId(null);

    try {
      const fd = new FormData();
      fd.append("video", file);
      fd.append("fps", String(fps));
      fd.append("max_frames", String(maxFrames));
      appendVideoRange(fd, range);

      const res = await fetch(`${UPLOAD_API}/exercise/from_video`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const id = data.id ?? data.exercise_id ?? data.exerciseId ?? String(data);
      setExerciseId(id);
      showStatus("info", `Cvičenie vytvorené. Načítavam snímky…`);
      await loadFrames(id);
    } catch (err) {
      showStatus("error", failureText("Nahranie zlyhalo", err));
    } finally {
      setUploading(false);
    }
  }, [fps, maxFrames, showStatus, clearStatus]);

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
      showStatus("success", `${pluralSk(normalised.length, "Načítaná", "Načítané", "Načítaných")} ${normalised.length} ${pluralSk(normalised.length, "snímka", "snímky", "snímok")}.`);
      return normalised;
    } catch (err) {
      showStatus("error", failureText("Načítanie snímok zlyhalo", err));
      return [];
    } finally {
      setLoadingFrames(false);
    }
  }, [showStatus]);

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
      showStatus("error", failureText("Vloženie zlyhalo", err));
    } finally {
      setInsertingAt(null);
    }
  }, [exerciseId, frames, loadFrames, generateDescription, showStatus]);

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
      showStatus("error", failureText("Odstránenie zlyhalo", err));
    } finally {
      setDeletingAt(null);
    }
  }, [exerciseId, frames, generateDescription, showStatus]);

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
      showStatus("error", failureText("Uloženie zlyhalo", err));
    }
  }, [exerciseId, frames, showStatus]);

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
  }, [exerciseId, showStatus]);

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
      showStatus("error", failureText("Spustenie zlyhalo", err));
    } finally {
      setRunning(false);
    }
  }, [exerciseId, showStatus]);

  // ── render ────────────────────────────────────────────────────
  return (
    <div className="w-full max-w-7xl mx-auto px-4 py-6 pb-24 space-y-6">

      <PageHeader
        title="Editor"
        description="Nahrajte video, upravte snímky, spustite na robotovi."
        actions={exerciseId && (
          <>
            <Button size="sm" variant="outline" onClick={resetEditor}>
              <Upload className="h-3.5 w-3.5" />
              Nahrať iné video
            </Button>
            <Button
              size="sm"
              variant={voiceEditOpen ? "secondary" : "outline"}
              onClick={() => setVoiceEditOpen((v) => !v)}
              disabled={!frames.length}
            >
              <Mic className="h-3.5 w-3.5" />
              Hlasová úprava
            </Button>
            <Button size="sm" onClick={runExercise} disabled={running || !frames.length}>
              {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              Spustiť na robotovi
            </Button>
          </>
        )}
      />

      <StatusAlert status={status} />

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
            <Input
              type="number"
              min={1}
              max={30}
              value={fps}
              onChange={(e) => setFps(Math.max(1, Math.min(30, Number(e.target.value))))}
              className="h-7 w-16 px-2 text-center"
            />
          </label>
          <label className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground whitespace-nowrap">Max snímok</span>
            <Input
              type="number"
              min={1}
              max={200}
              value={maxFrames}
              onChange={(e) => setMaxFrames(Math.max(1, Math.min(200, Number(e.target.value))))}
              className="h-7 w-16 px-2 text-center"
            />
          </label>
        </div>
      )}

      {/* ── range selection ── */}
      {!exerciseId && pending.file && pending.url && (
        <SelectedFileCard
          file={pending.file}
          onClear={clearPendingVideo}
          onSubmit={() => handleUpload(pending.file!, videoRange)}
          submitLabel={uploading ? "Spracovanie videa…" : "Spracovať vybranú časť"}
          submitting={uploading}
          submitDisabled={!videoRange}
        >
          <VideoTrimmer key={pending.url} src={pending.url} onChange={setVideoRange} />
        </SelectedFileCard>
      )}

      {/* ── upload zone (shown when no exercise loaded) ── */}
      {!exerciseId && !pending.file && (
        <FileDropzone
          onFile={selectVideo}
          accept="video/*"
          formats="MP4, MOV, AVI, WEBM"
        />
      )}

      {/* ── exercise name and AI estimates ── */}
      {exerciseId && (
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <ExerciseNameInput name={exerciseName} onRename={renameExercise} className="w-64" />
            {caloriesLoading ? (
              <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Odhadovanie kalórií…
              </span>
            ) : calories != null ? (
              <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                <Flame className="h-3.5 w-3.5" />
                {calories} kcal
                <Badge variant="secondary" className="px-1.5 py-0 text-[10px] font-normal">Odhad AI</Badge>
              </span>
            ) : null}
          </div>
          {descLoading ? (
            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Generovanie popisu pomocou AI…
            </span>
          ) : description ? (
            <p className="max-w-3xl text-xs leading-relaxed text-muted-foreground">{description}</p>
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
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-medium text-foreground">Snímky</h2>
            <Badge variant="secondary" className="tabular-nums">{frames.length}</Badge>
            <p className="ml-2 flex items-center gap-1 text-xs text-muted-foreground">
              <GripVertical className="h-3.5 w-3.5" />
              Poradie zmeníte pretiahnutím
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
    <div className="px-3 pt-1.5 relative">
      {count > 0 ? (
        <span
          className="text-[11px] text-muted-foreground underline decoration-dotted underline-offset-2 cursor-default hover:text-foreground transition-colors"
          onMouseEnter={show}
          onMouseLeave={hide}
        >
          Uhly
        </span>
      ) : (
        <span className="text-[11px] italic text-muted-foreground">žiadne dáta uhlov</span>
      )}
      {open && count > 0 && (
        <div
          className="absolute bottom-full left-3 mb-1 w-56 z-50 rounded-lg border bg-popover text-popover-foreground shadow-lg p-2"
          onMouseEnter={show}
          onMouseLeave={hide}
        >
          <p className="px-1 pb-1.5 mb-1 border-b text-[11px] font-medium">Uhly kĺbov (rad)</p>
          <div className="max-h-52 overflow-y-auto">
            {Object.entries(angles).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3 rounded px-1 py-0.5 text-[11px] hover:bg-muted">
                <span className="text-muted-foreground">{k}</span>
                <span className="font-mono tabular-nums">{typeof v === "number" ? v.toFixed(3) : v}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── FrameCard sub-component ───────────────────────────────────────
const MENU_CONTENT = "z-50 min-w-44 rounded-md border bg-popover p-1 text-popover-foreground shadow-md";
const MENU_ITEM = "flex items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none cursor-default select-none data-[highlighted]:bg-accent data-[disabled]:opacity-50 data-[disabled]:pointer-events-none";

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
  showStatus: (type: StatusType, text: string) => void;
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
  ...dragProps
}: FrameCardProps) {
  // ── voice lines, saved on blur, after dictation and on voice change ──
  const [voiceText, setVoiceText] = useState("");
  const [speechLanguage, setSpeechLanguage] = useState<string>(DEFAULT_SPEECH_LANGUAGE);
  const [speechSpeed, setSpeechSpeed] = useState<number>(DEFAULT_SPEECH_SPEED);
  const [voiceSaved, setVoiceSaved] = useState(false);
  const [dictation, setDictation] = useState<"idle" | "recording" | "transcribing">("idle");
  const [naoSaying, setNaoSaying] = useState(false);
  // server config, keeps fields card does not edit
  const storedVoiceConfig = useRef<VoiceLinesConfig>({});
  const savedVoiceText = useRef("");
  const recorder = useRef<MediaRecorder | null>(null);
  const voiceConfigUrl = `${EDITOR_API}/voiceLines/config/exercise/${exerciseId}/frame/${frame.idx}`;

  useEffect(() => {
    fetch(voiceConfigUrl)
      .then((res) => (res.ok ? res.json() : {}))
      .then((config: VoiceLinesConfig) => {
        storedVoiceConfig.current = config;
        const text = voiceTextFromConfig(config);
        savedVoiceText.current = text;
        setVoiceText(text);
        if (config.lang) setSpeechLanguage(config.lang);
        if (config.speed !== undefined) setSpeechSpeed(Number(config.speed));
      })
      .catch(() => {/* no voice lines yet */});
  }, [voiceConfigUrl]);

  // release microphone when card unmounts mid-recording
  useEffect(() => () => recorder.current?.stream.getTracks().forEach((track) => track.stop()), []);

  const saveVoice = async (text: string, lang = speechLanguage, speed = speechSpeed) => {
    const config: VoiceLinesConfig = {
      ...storedVoiceConfig.current,
      extractedText: hasVoiceText(text) ? text : NO_VOICE_TEXT,
      lang,
      speed,
    };
    try {
      const res = await fetch(voiceConfigUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice_lines: config }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      storedVoiceConfig.current = config;
      savedVoiceText.current = text;
      setVoiceSaved(true);
      setTimeout(() => setVoiceSaved(false), 2000);
    } catch (err) {
      showStatus("error", failureText("Uloženie textu zlyhalo", err));
    }
  };

  const changeSpeech = (lang: string, speed: number) => {
    setSpeechLanguage(lang);
    setSpeechSpeed(speed);
    saveVoice(voiceText, lang, speed);
  };

  // record voice, transcribe, append text to field
  const toggleDictation = async () => {
    if (dictation === "recording") {
      recorder.current?.stop();
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      showStatus("error", "Mikrofón nie je dostupný.");
      return;
    }
    const chunks: Blob[] = [];
    const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
    mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      setDictation("transcribing");
      try {
        const audio = await blobToBase64(new Blob(chunks, { type: "audio/webm" }));
        const res = await fetch(`${TO_TEXT_API}/translate/webm`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ audio_file: audio, model: "large-v1" }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const { translation } = await res.json();
        if (translation) {
          const text = voiceText.trim() ? `${voiceText.trim()} ${translation}` : translation;
          setVoiceText(text);
          saveVoice(text);
        }
      } catch (err) {
        showStatus("error", failureText("Prepis reči zlyhal", err));
      } finally {
        setDictation("idle");
      }
    };
    recorder.current = mediaRecorder;
    mediaRecorder.start();
    setDictation("recording");
  };

  // robot says text now, nothing saved
  const sayOnRobot = async () => {
    const voice_lines_configs = hasVoiceText(voiceText)
      ? { entire: { translation: voiceText } }
      : storedVoiceConfig.current.voice_lines_configs;
    if (!voice_lines_configs || Object.keys(voice_lines_configs).length === 0) {
      showStatus("info", "Najprv napíšte, čo má robot povedať.");
      return;
    }
    setNaoSaying(true);
    try {
      const res = await fetch(`${ROBOT_API}/voiceLines/applyVoiceLine`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice_lines: { voice_lines_configs, lang: speechLanguage, speed: speechSpeed } }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    } catch (err) {
      showStatus("error", failureText("Robot nemohol hovoriť", err));
    } finally {
      setNaoSaying(false);
    }
  };

  // shared by mobile and desktop layouts
  const frameMenu = (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label="Možnosti snímky" disabled={inserting || deleting}>
          {inserting || deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <MoreHorizontal className="h-4 w-4" />}
        </Button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="end" sideOffset={4} className={MENU_CONTENT}>
          {([["Vložiť pózu pred", onInsertBefore, ChevronLeft], ["Vložiť pózu za", onInsertAfter, ChevronRight]] as const).map(
            ([label, onInsert, Icon]) => (
              <DropdownMenu.Sub key={label}>
                <DropdownMenu.SubTrigger className={MENU_ITEM} disabled={poses.length === 0}>
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  {label}
                  <ChevronRight className="h-4 w-4 ml-auto text-muted-foreground" />
                </DropdownMenu.SubTrigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.SubContent sideOffset={4} className={`${MENU_CONTENT} max-h-72 overflow-y-auto`}>
                    {poses.map((p) => (
                      <DropdownMenu.Item key={p.name} className={MENU_ITEM} onSelect={() => onInsert(p.name)}>
                        {poseLabel(p.name)}
                      </DropdownMenu.Item>
                    ))}
                  </DropdownMenu.SubContent>
                </DropdownMenu.Portal>
              </DropdownMenu.Sub>
            )
          )}
          <DropdownMenu.Separator className="my-1 h-px bg-border" />
          <RadioSubmenu
            icon={Languages}
            label="Jazyk reči"
            value={speechLanguage}
            options={SPEECH_LANGUAGES}
            onChange={(lang) => changeSpeech(lang, speechSpeed)}
          />
          <RadioSubmenu
            icon={Gauge}
            label="Rýchlosť reči"
            value={String(speechSpeed)}
            options={SPEECH_SPEEDS.map((speed) => [String(speed), `${speed} %`])}
            onChange={(speed) => changeSpeech(speechLanguage, Number(speed))}
          />
          <DropdownMenu.Separator className="my-1 h-px bg-border" />
          <DropdownMenu.Item className={`${MENU_ITEM} text-destructive data-[highlighted]:text-destructive`} onSelect={onDelete}>
            <Trash2 className="h-4 w-4" />
            Odstrániť snímku
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );

  return (
    <div
      {...dragProps}
      className={[
        "w-full md:w-60 md:shrink-0 rounded-xl border bg-card text-card-foreground shadow-sm",
        "transition-all duration-150 cursor-grab active:cursor-grabbing",
        deleting ? "opacity-40 pointer-events-none" : "",
      ].join(" ")}
    >
      {/* ── mobile: compact horizontal row ── */}
      <div className="flex md:hidden items-center gap-3 px-3 py-2">
        <FrameImage frame={frame} exerciseId={exerciseId} className="w-14 h-14 shrink-0 object-cover" />
        <span className="text-sm font-medium text-foreground tabular-nums">{position + 1}</span>
        <div className="ml-auto flex items-center gap-1">
          <GripVertical className="h-4 w-4 text-muted-foreground/40" />
          {frameMenu}
        </div>
      </div>

      {/* ── desktop: vertical card ── */}
      <div className="hidden md:flex flex-col h-full">
        {/* header */}
        <div className="flex items-center gap-1 pl-3 pr-1.5 pt-1.5 pb-1">
          <span className="text-sm font-medium text-foreground tabular-nums">{position + 1}</span>
          <GripVertical className="h-4 w-4 ml-auto text-muted-foreground/40" />
          {frameMenu}
        </div>

        <div className="px-3 flex-1">
          <FrameImage frame={frame} exerciseId={exerciseId} className="w-full min-h-32" />
        </div>

        <AnglesTooltip angles={frame.angles} />

        <div className="mt-auto">
          <div className="px-3 pt-5 pb-3 flex flex-col gap-2">
            <label htmlFor={`voice-text-${frame.idx}`} className="text-xs font-medium text-foreground">
              Čo povie NAO
            </label>
            <Textarea
              id={`voice-text-${frame.idx}`}
              placeholder="Napíšte alebo nadiktujte…"
              value={voiceText}
              onChange={(e) => setVoiceText(e.target.value)}
              onBlur={() => { if (voiceText !== savedVoiceText.current) saveVoice(voiceText); }}
              disabled={dictation !== "idle"}
              className="min-h-18 resize-none px-2 py-1.5 text-xs md:text-xs"
            />
            <div className="flex items-center gap-1">
              <Button
                variant={dictation === "recording" ? "destructive" : "ghost"}
                size="icon-sm"
                onClick={toggleDictation}
                disabled={dictation === "transcribing"}
                aria-label={dictation === "recording" ? "Zastaviť diktovanie" : "Diktovať text"}
                title={dictation === "recording" ? "Zastaviť diktovanie" : "Diktovať text"}
              >
                {dictation === "transcribing"
                  ? <Loader2 className="h-4 w-4 animate-spin" />
                  : dictation === "recording" ? <Square className="h-3.5 w-3.5" /> : <Mic className="h-4 w-4" />}
              </Button>
              <span className="truncate text-[11px] text-muted-foreground" aria-live="polite">
                {dictation === "recording" ? "Nahrávam…" : dictation === "transcribing" ? "Prepisujem…" : voiceSaved ? "Uložené" : ""}
              </span>
              <Button variant="outline" size="sm" className="ml-auto shrink-0" onClick={sayOnRobot} disabled={naoSaying}>
                {naoSaying ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                Povedz
              </Button>
            </div>
          </div>
        </div>
      </div>{/* end desktop card */}
    </div>
  );
}

// Frame photo, then pose image, then placeholder
function FrameImage({ frame, exerciseId, className }: { frame: Frame; exerciseId: string; className: string }) {
  const sources = [
    `${EDITOR_API}/exercise/${exerciseId}/frame/${frame.idx}/image`,
    frame.pose_name ? `${POSES_API}/pose/${frame.pose_name}/image` : null,
  ].filter((src): src is string => src !== null);
  const [failed, setFailed] = useState(0);

  if (failed >= sources.length) {
    return (
      <div className={`${className} rounded-lg bg-muted flex items-center justify-center`}>
        <Film className="h-5 w-5 text-muted-foreground/40" />
      </div>
    );
  }
  return (
    <img
      src={sources[failed]}
      alt={frame.pose_name ?? `Snímka ${frame.idx}`}
      className={`${className} rounded-lg bg-muted`}
      onError={() => setFailed((n) => n + 1)}
    />
  );
}

type RadioSubmenuProps = {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  options: [string, string][];
  onChange: (value: string) => void;
};

function RadioSubmenu({ icon: Icon, label, value, options, onChange }: RadioSubmenuProps) {
  return (
    <DropdownMenu.Sub>
      <DropdownMenu.SubTrigger className={MENU_ITEM}>
        <Icon className="h-4 w-4 text-muted-foreground" />
        {label}
        <ChevronRight className="h-4 w-4 ml-auto text-muted-foreground" />
      </DropdownMenu.SubTrigger>
      <DropdownMenu.Portal>
        <DropdownMenu.SubContent sideOffset={4} className={MENU_CONTENT}>
          <DropdownMenu.RadioGroup value={value} onValueChange={onChange}>
            {options.map(([optionValue, optionLabel]) => (
              <DropdownMenu.RadioItem key={optionValue} value={optionValue} className={MENU_ITEM}>
                <span className="w-4">
                  <DropdownMenu.ItemIndicator><Check className="h-4 w-4" /></DropdownMenu.ItemIndicator>
                </span>
                {optionLabel}
              </DropdownMenu.RadioItem>
            ))}
          </DropdownMenu.RadioGroup>
        </DropdownMenu.SubContent>
      </DropdownMenu.Portal>
    </DropdownMenu.Sub>
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
    <Card className="gap-4 px-6">
      <div className="flex items-start gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground">Hlasová úprava</p>
          <p className="text-xs text-muted-foreground mt-0.5 flex flex-wrap items-center gap-2">
            <span>Povedzte napr. <span className="italic">„vlož drep za snímku 3“</span>.</span>
            <AiBadge />
          </p>
        </div>
        <Button variant="ghost" size="icon-sm" className="ml-auto -mt-1 -mr-2 shrink-0" onClick={onClose} aria-label="Zavrieť">
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex flex-col items-center gap-2 py-2">
        <MicButton size="md" listening={listening} onClick={listening ? stopListening : startListening} />
        <p className="text-xs text-muted-foreground">
          {listening ? "Počúvam… klepnite pre zastavenie" : "Klepnite pre hovorenie"}
        </p>
      </div>

      {(transcript || phase === "error") && (
        <TranscriptBlock
          transcript={transcript}
          pending={phase === "parsing"}
          error={phase === "error" ? errorMsg : undefined}
          result={
            phase === "confirm" && parsed?.pose ? (
              <p className="text-sm text-foreground">
                Vložiť <strong>{poseLabel(parsed.pose)}</strong> {parsed.side === "before" ? "pred" : "za"} snímku <strong>{parsed.frame}</strong>
              </p>
            ) : phase === "pick_pose" && parsed ? (
              // frame and side known, pose unclear
              <div className="space-y-2">
                <p className="text-sm text-foreground">
                  Snímka <strong>{parsed.frame}</strong>, {parsed.side === "before" ? "pred" : "za"}. Vyberte pózu:
                </p>
                <NativeSelect
                  className="max-w-xs"
                  value={pickedPose}
                  onChange={(e) => setPickedPose(e.target.value)}
                >
                  <option value="" disabled>Póza…</option>
                  {poses.map((p) => (
                    <option key={p.name} value={p.name}>{poseLabel(p.name)}</option>
                  ))}
                </NativeSelect>
              </div>
            ) : null
          }
          actions={
            phase === "idle" && !listening ? (
              <>
                <Button size="sm" onClick={parseWithLLM}>Rozpoznať príkaz</Button>
                <Button size="sm" variant="outline" onClick={reset}>Zrušiť</Button>
              </>
            ) : phase === "confirm" || phase === "pick_pose" ? (
              <>
                <Button size="sm" disabled={phase === "pick_pose" && !pickedPose} onClick={() => confirm(phase === "pick_pose" ? pickedPose : undefined)}>
                  <Check className="h-3.5 w-3.5" />Potvrdiť
                </Button>
                <Button size="sm" variant="outline" onClick={reset}>Skúsiť znova</Button>
              </>
            ) : phase === "error" ? (
              <Button size="sm" variant="outline" onClick={reset}>Skúsiť znova</Button>
            ) : null
          }
        />
      )}
    </Card>
  );
}