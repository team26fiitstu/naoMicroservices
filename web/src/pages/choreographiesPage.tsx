import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CalendarDays, FolderOpen, Loader2, Plus, Trash2, Workflow } from "lucide-react";
import { Page } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirmDialog";
import { EmptyState } from "@/components/ui/emptyState";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/ui/loadingState";
import { MetaItem, MetaRow } from "@/components/ui/meta";
import { NameInput } from "@/components/ui/nameInput";
import { StatusAlert } from "@/components/ui/statusAlert";
import { ExerciseSelect } from "@/components/exercise/exerciseSelect";
import { useStatus } from "@/hooks/useStatus";
import { createChoreography, deleteChoreography, listChoreographies, newState, renameChoreography, type ChoreographySummary } from "@/lib/choreography";
import { formatDateTime } from "@/lib/date";
import { failureText } from "@/lib/errors";
import { exerciseDisplayName } from "@/lib/exerciseName";
import { listExercises, type ExerciseSummary } from "@/lib/exercises";
import { pluralSk } from "@/lib/plural";

export default function ChoreographiesPage() {
  const [choreographies, setChoreographies] = useState<ChoreographySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [toDelete, setToDelete] = useState<ChoreographySummary | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const { status, show: showStatus } = useStatus();
  const navigate = useNavigate();

  const load = useCallback(async () => {
    try {
      setChoreographies(await listChoreographies());
    } catch (err) {
      showStatus("error", failureText("Načítanie choreografií zlyhalo", err));
    } finally {
      setLoading(false);
    }
  }, [showStatus]);

  useEffect(() => { load(); }, [load]);

  const rename = async (id: string, name: string) => {
    try {
      const { updated_at } = await renameChoreography(id, name);
      setChoreographies((list) => list.map((c) => (c.id === id ? { ...c, name, updated_at } : c)));
      return true;
    } catch (err) {
      showStatus("error", failureText("Premenovanie zlyhalo", err));
      return false;
    }
  };

  const remove = async (id: string) => {
    setDeleting(id);
    try {
      await deleteChoreography(id);
      setChoreographies((list) => list.filter((c) => c.id !== id));
      showStatus("success", "Choreografia odstránená, cvičenia zostali.");
    } catch (err) {
      showStatus("error", failureText("Odstránenie zlyhalo", err));
    } finally {
      setDeleting(null);
    }
  };

  // stable, create form loads exercises once with it
  const reportError = useCallback((action: string, err: unknown) => showStatus("error", failureText(action, err)), [showStatus]);

  const newButton = (
    <Button size="sm" onClick={() => setCreating(true)} disabled={creating}>
      <Plus className="h-3.5 w-3.5" />
      Nová choreografia
    </Button>
  );

  return (
    <Page title="Choreografie" description="Grafy stavov, v ktorých sú stavy uložené cvičenia." actions={newButton}>
      <StatusAlert status={status} />

      {creating && (
        <CreateForm
          onCancel={() => setCreating(false)}
          onCreated={(id) => navigate(`/choreographies/${id}`)}
          onError={reportError}
        />
      )}

      {loading && <LoadingState text="Načítavam choreografie…" />}

      {!loading && !creating && choreographies.length === 0 && (
        <EmptyState icon={Workflow} text="Zatiaľ žiadne choreografie." action={newButton} />
      )}

      {!loading && choreographies.map((c) => (
        <Card key={c.id} className="flex-col gap-4 px-5 py-4 sm:flex-row sm:items-start">
          <div className="min-w-0 flex-1 space-y-1.5">
            <NameInput name={c.name} label="Názov choreografie" onRename={(name) => rename(c.id, name)} className="w-full max-w-sm" />
            <MetaRow>
              <MetaItem icon={Workflow}>{c.state_count} {pluralSk(c.state_count, "stav", "stavy", "stavov")}</MetaItem>
              <MetaItem icon={CalendarDays}>{formatDateTime(c.updated_at)}</MetaItem>
            </MetaRow>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Button size="sm" variant="outline" onClick={() => navigate(`/choreographies/${c.id}`)}>
              <FolderOpen className="h-3.5 w-3.5" />
              Otvoriť
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setToDelete(c)}
              disabled={deleting === c.id}
              aria-label="Odstrániť choreografiu"
              title="Odstrániť choreografiu"
              className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
            >
              {deleting === c.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            </Button>
          </div>
        </Card>
      ))}

      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(open) => { if (!open) setToDelete(null); }}
        title="Odstrániť choreografiu?"
        description={`Choreografia „${toDelete?.name}“ sa natrvalo odstráni. Cvičenia v nej zostanú.`}
        confirmLabel="Odstrániť"
        onConfirm={() => { if (toDelete) remove(toDelete.id); }}
      />
    </Page>
  );
}

type CreateFormProps = {
  onCancel: () => void;
  onCreated: (id: string) => void;
  onError: (action: string, err: unknown) => void;
};

// graph needs at least one state, chosen exercise becomes initial state
function CreateForm({ onCancel, onCreated, onError }: CreateFormProps) {
  const [exercises, setExercises] = useState<ExerciseSummary[]>([]);
  const [name, setName] = useState("");
  const [exerciseId, setExerciseId] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    listExercises().then(setExercises).catch((err) => onError("Načítanie cvičení zlyhalo", err));
  }, [onError]);

  const create = async () => {
    const exercise = exercises.find((e) => e.id === exerciseId);
    if (!name.trim() || !exercise) return;
    setSaving(true);
    try {
      const initial = newState([], exercise.id, exerciseDisplayName(exercise.name));
      const created = await createChoreography({ name: name.trim(), initial_state: initial.id, states: [initial], transitions: [] });
      onCreated(created.id);
    } catch (err) {
      onError("Vytvorenie zlyhalo", err);
      setSaving(false);
    }
  };

  return (
    <Card className="gap-4 px-6">
      <p className="text-sm font-medium text-foreground">Nová choreografia</p>
      <div className="flex flex-wrap gap-2">
        <Input className="max-w-xs" placeholder="Názov" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        <ExerciseSelect
          className="max-w-xs"
          exercises={exercises}
          value={exerciseId}
          onValueChange={setExerciseId}
          placeholder="Počiatočný stav…"
          emptyText="Najprv vytvorte cvičenie"
        />
      </div>
      <div className="flex gap-2">
        <Button size="sm" onClick={create} disabled={saving || !name.trim() || !exerciseId}>
          {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Vytvoriť
        </Button>
        <Button size="sm" variant="outline" onClick={onCancel} disabled={saving}>Zrušiť</Button>
      </div>
    </Card>
  );
}
