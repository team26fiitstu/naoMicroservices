import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MetaItem, MetaRow } from "@/components/ui/meta";
import { ExerciseNameInput } from "@/components/exercise/exerciseNameInput";
import { ConfirmDialog } from "@/components/ui/confirmDialog";
import { EmptyState } from "@/components/ui/emptyState";
import { LoadingState } from "@/components/ui/loadingState";
import { exerciseDisplayName } from "@/lib/exerciseName";
import { StatusAlert } from "@/components/ui/statusAlert";
import { Page } from "@/components/layout/page";
import { useStatus } from "@/hooks/useStatus";
import { pluralSk } from "@/lib/plural";
import { api, ApiError } from "@/lib/api";
import { failureText } from "@/lib/errors";
import { formatDateTime } from "@/lib/date";
import { listExercises, runExercise, updateExercise, type ExerciseSummary } from "@/lib/exercises";
import { Loader2, Play, Trash2, Film, CalendarDays, Flame, FolderOpen, Upload } from "lucide-react";

export default function ExercisesPage() {
  const [exercises, setExercises] = useState<ExerciseSummary[]>([]);
  const [loading, setLoading]     = useState(true);
  const { status, show: showStatus } = useStatus();
  const [running, setRunning]     = useState<string | null>(null);
  const [deleting, setDeleting]   = useState<string | null>(null);
  const [toDelete, setToDelete]   = useState<ExerciseSummary | null>(null);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setExercises(await listExercises());
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
      await api(`/exercise/${id}`, { method: "DELETE" });
      setExercises((prev) => prev.filter((e) => e.id !== id));
      showStatus("success", "Cvičenie odstránené.");
    } catch (err) {
      // 409: used in choreography, Slovak message from names instead of English server error
      if (err instanceof ApiError && err.status === 409) {
        const body = err.body as { choreographies?: { name: string }[] } | undefined;
        const names = (body?.choreographies ?? []).map((c) => c.name).filter(Boolean);
        showStatus("error", names.length > 0
          ? `Cvičenie sa používa v choreografii: ${names.join(", ")}.`
          : "Cvičenie sa používa v choreografii a nedá sa odstrániť.");
      } else {
        showStatus("error", failureText("Odstránenie zlyhalo", err));
      }
    } finally {
      setDeleting(null);
    }
  };

  const handleRun = async (id: string) => {
    setRunning(id);
    try {
      await runExercise(id);
      showStatus("success", "Cvičenie odoslané robotovi!");
    } catch (err) {
      showStatus("error", failureText("Spustenie zlyhalo", err));
    } finally {
      setRunning(null);
    }
  };

  const renameExercise = async (id: string, name: string) => {
    try {
      await updateExercise(id, { name });
      setExercises((prev) => prev.map((e) => e.id === id ? { ...e, name } : e));
      return true;
    } catch (err) {
      showStatus("error", failureText("Premenovanie zlyhalo", err));
      return false;
    }
  };

  return (
    <Page title="Cvičenia" description="Všetky uložené cvičenia">
      <StatusAlert status={status} />

      {loading && <LoadingState text="Načítavam cvičenia…" />}

      {!loading && exercises.length === 0 && (
        <EmptyState
          text="Zatiaľ žiadne cvičenia."
          action={
            <Button size="sm" variant="outline" onClick={() => navigate("/upload")}>
              <Upload className="h-3.5 w-3.5" />
              Nahrať video
            </Button>
          }
        />
      )}

      {!loading && exercises.map((ex) => (
        <Card key={ex.id} className="flex-col gap-4 px-5 py-4 sm:flex-row sm:items-start">
          <div className="min-w-0 flex-1 space-y-1.5">
            <ExerciseNameInput name={ex.name} onRename={(name) => renameExercise(ex.id, name)} className="w-full max-w-sm" />

            <MetaRow>
              <MetaItem icon={Film}>{ex.frame_count} {pluralSk(ex.frame_count, "snímka", "snímky", "snímok")}</MetaItem>
              <MetaItem icon={CalendarDays}>{formatDateTime(ex.created_at)}</MetaItem>
              {ex.calories != null && (
                <MetaItem icon={Flame}>
                  {ex.calories} kcal
                  <Badge variant="secondary" className="px-1.5 py-0 text-[10px] font-normal">Odhad AI</Badge>
                </MetaItem>
              )}
            </MetaRow>

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
    </Page>
  );
}
