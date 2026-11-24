import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ExerciseNameInput } from "@/components/exercise/exerciseNameInput";
import { ConfirmDialog } from "@/components/ui/confirmDialog";
import { exerciseDisplayName } from "@/lib/exerciseName";
import { StatusAlert } from "@/components/ui/statusAlert";
import { PageHeader } from "@/components/layout/pageHeader";
import { useStatus } from "@/hooks/useStatus";
import { pluralSk } from "@/lib/plural";
import { API_BASE } from "@/lib/api";
import { failureText } from "@/lib/errors";
import { Loader2, Play, Trash2, Film, CalendarDays, Flame, FolderOpen, Upload } from "lucide-react";

// created_at is UTC without timezone suffix
const formatCreatedAt = (value: string) =>
  new Date(/Z|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`).toLocaleString("sk-SK", {
    day: "numeric", month: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit",
  });

type Exercise = {
  id: string;
  name: string;
  frame_count: number;
  created_at: string;
  repetitions: number;
  calories?: number | null;
  description?: string | null;
};

export default function ExercisesStore() {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [loading, setLoading]     = useState(true);
  const { status, show: showStatus } = useStatus();
  const [running, setRunning]     = useState<string | null>(null);
  const [deleting, setDeleting]   = useState<string | null>(null);
  const [toDelete, setToDelete]   = useState<Exercise | null>(null);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/exercise/list`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setExercises(await res.json());
    } catch (err) {
      showStatus("error", failureText("Načítanie cvičení zlyhalo", err));
    } finally {
      setLoading(false);
    }
  }, [showStatus]);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async (id: string) => {
    setDeleting(id);
    try {
      const res = await fetch(`${API_BASE}/exercise/${id}`, { method: "DELETE" });
      if (!res.ok) {
        if (res.status === 409) {
          // The backend's "error" field is an English technical message; build
          // a Slovak message from the structured "choreographies" list instead.
          const body = await res.json().catch(() => null) as { choreographies?: { id: string; name: string }[] } | null;
          const names = (body?.choreographies ?? []).map((c) => c.name).filter(Boolean);
          throw new Error(
            names.length > 0
              ? `Cvičenie sa používa v choreografii: ${names.join(", ")}.`
              : "Cvičenie sa používa v choreografii a nedá sa odstrániť.",
          );
        }
        throw new Error(`HTTP ${res.status}`);
      }
      setExercises((prev) => prev.filter((e) => e.id !== id));
      showStatus("success", "Cvičenie odstránené.");
    } catch (err) {
      showStatus("error", failureText("Odstránenie zlyhalo", err));
    } finally {
      setDeleting(null);
    }
  };

  const handleRun = async (id: string) => {
    setRunning(id);
    try {
      const res = await fetch(`${API_BASE}/exercise/${id}/run`, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showStatus("success", "Cvičenie odoslané robotovi!");
    } catch (err) {
      showStatus("error", failureText("Spustenie zlyhalo", err));
    } finally {
      setRunning(null);
    }
  };

  const renameExercise = async (id: string, name: string) => {
    try {
      const res = await fetch(`${API_BASE}/exercise/${id}/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setExercises((prev) => prev.map((e) => e.id === id ? { ...e, name } : e));
      return true;
    } catch (err) {
      showStatus("error", failureText("Premenovanie zlyhalo", err));
      return false;
    }
  };

  return (
    <div className="w-full max-w-7xl mx-auto px-4 py-6 pb-24 space-y-4">
      <PageHeader title="Cvičenia" description="Všetky uložené cvičenia" />
      <StatusAlert status={status} />

      {loading && (
        <div className="flex justify-center py-16">
          <Loader2 className="h-7 w-7 text-primary animate-spin" />
        </div>
      )}

      {!loading && exercises.length === 0 && (
        <Card className="flex flex-col items-center justify-center py-16 gap-3">
          <Film className="h-8 w-8 text-muted-foreground opacity-40" />
          <p className="text-sm text-muted-foreground">Zatiaľ žiadne cvičenia.</p>
          <Button size="sm" variant="outline" onClick={() => navigate("/upload")}>
            <Upload className="h-3.5 w-3.5" />
            Nahrať video
          </Button>
        </Card>
      )}

      {!loading && exercises.map((ex) => (
        <Card key={ex.id} className="flex-col gap-4 px-5 py-4 sm:flex-row sm:items-start">
          <div className="min-w-0 flex-1 space-y-1.5">
            <ExerciseNameInput name={ex.name} onRename={(name) => renameExercise(ex.id, name)} className="w-full max-w-sm" />

            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1.5">
                <Film className="h-3.5 w-3.5" />
                {ex.frame_count} {pluralSk(ex.frame_count, "snímka", "snímky", "snímok")}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <CalendarDays className="h-3.5 w-3.5" />
                {formatCreatedAt(ex.created_at)}
              </span>
              {ex.calories != null && (
                <span className="inline-flex items-center gap-1.5">
                  <Flame className="h-3.5 w-3.5" />
                  {ex.calories} kcal
                  <Badge variant="secondary" className="px-1.5 py-0 text-[10px] font-normal">Odhad AI</Badge>
                </span>
              )}
            </div>

            {ex.description && (
              <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">{ex.description}</p>
            )}
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <Button size="sm" variant="outline" onClick={() => navigate(`/edit?id=${ex.id}`)}>
              <FolderOpen className="h-3.5 w-3.5" />
              Otvoriť
            </Button>
            <Button size="sm" onClick={() => handleRun(ex.id)} disabled={running === ex.id}>
              {running === ex.id
                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                : <Play className="h-3.5 w-3.5" />}
              Spustiť
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setToDelete(ex)}
              disabled={deleting === ex.id}
              aria-label="Odstrániť cvičenie"
              title="Odstrániť cvičenie"
              className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
            >
              {deleting === ex.id
                ? <Loader2 className="h-4 w-4 animate-spin" />
                : <Trash2 className="h-4 w-4" />}
            </Button>
          </div>
        </Card>
      ))}

      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(open) => { if (!open) setToDelete(null); }}
        title="Odstrániť cvičenie?"
        description={`Cvičenie „${exerciseDisplayName(toDelete?.name)}“ sa natrvalo odstráni.`}
        confirmLabel="Odstrániť"
        onConfirm={() => { if (toDelete) handleDelete(toDelete.id); }}
      />
    </div>
  );
}
