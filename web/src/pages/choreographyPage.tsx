import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Loader2, Move, Play, Plus, Square, Workflow } from "lucide-react";
import { Page } from "@/components/layout/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirmDialog";
import { EmptyState } from "@/components/ui/emptyState";
import { LoadingState } from "@/components/ui/loadingState";
import { NameInput } from "@/components/ui/nameInput";
import { StatusAlert } from "@/components/ui/statusAlert";
import { AddStatePanel } from "@/components/choreography/addStatePanel";
import { GraphCanvas } from "@/components/choreography/graphCanvas";
import { GraphInspector } from "@/components/choreography/graphInspector";
import { RunPanel } from "@/components/choreography/runPanel";
import { useChoreography } from "@/hooks/useChoreography";
import { useChoreographyRun } from "@/hooks/useChoreographyRun";
import type { ChoreographyState, GraphSelection } from "@/lib/choreography";
import { failureText } from "@/lib/errors";

// keyed by id, so selection and panels start fresh for each choreography
export default function ChoreographyPage() {
  const { id = "" } = useParams();
  return <ChoreographyView key={id} id={id} />;
}

function ChoreographyView({ id }: { id: string }) {
  const navigate = useNavigate();
  const choreography = useChoreography(id);
  const { graph, exercises, loading, failed, showStatus } = choreography;
  const control = useChoreographyRun(id, showStatus);
  const { run } = control;
  const [selection, setSelection] = useState<GraphSelection>(null);
  const [adding, setAdding] = useState(false);
  const [toRemove, setToRemove] = useState<ChoreographyState | null>(null);

  const exerciseById = useMemo(() => new Map(exercises.map((e) => [e.id, e])), [exercises]);
  const openInEditor = (stateId: string) => navigate(`/edit?id=${stateId}`);

  return (
    <Page
      title="Choreografia"
      description="Rozložte stavy, nastavte počiatočný a otvorte stav v editore."
      fill
      actions={graph && (run ? (
        <Button size="sm" variant="outline" onClick={control.stop} disabled={control.sending}>
          <Square className="h-3.5 w-3.5" />
          Zastaviť
        </Button>
      ) : (
        <>
          <Button size="sm" variant={adding ? "secondary" : "outline"} onClick={() => setAdding((open) => !open)}>
            <Plus className="h-3.5 w-3.5" />
            Pridať stav
          </Button>
          <Button
            size="sm"
            onClick={() => { setAdding(false); setSelection(null); control.start(); }}
            disabled={control.sending}
          >
            {control.sending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            Spustiť
          </Button>
        </>
      ))}
    >
      <StatusAlert status={choreography.status} />

      {graph && <NameInput name={graph.name} label="Názov choreografie" onRename={choreography.rename} className="w-64" />}

      {adding && graph && !run && (
        <AddStatePanel
          exercises={exercises.filter((e) => !graph.states.some((s) => s.state_id === e.id))}
          onAddExisting={choreography.addState}
          onAddNew={choreography.addNewExercise}
          onError={(action, err) => showStatus("error", failureText(action, err))}
          onReject={() => showStatus("error", "Vyberte video alebo obrázok.")}
          onClose={() => setAdding(false)}
        />
      )}

      {loading && !graph && <LoadingState text="Načítavam choreografiu…" className="fill-screen:flex-1" />}

      {!loading && failed && (
        <EmptyState
          className="fill-screen:flex-1"
          icon={Workflow}
          text="Choreografiu sa nepodarilo načítať."
          action={<Button variant="outline" size="sm" onClick={choreography.reload}>Skúsiť znova</Button>}
        />
      )}

      {graph && (
        <div className="space-y-3 fill-screen:flex fill-screen:flex-1 fill-screen:flex-col">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-medium text-foreground">Stavy</h2>
            <Badge variant="secondary" className="tabular-nums">{graph.states.length}</Badge>
            <p className="ml-2 flex items-center gap-1 text-xs text-muted-foreground">
              <Move className="h-3.5 w-3.5" />
              {run ? "Klik na zelený prechod pošle signál" : "Stavy presúvate ťahaním"}
            </p>
          </div>
          <div className="grid grid-cols-1 gap-(--layout-gap) fill-screen:flex-1 lg:grid-cols-[1fr_280px]">
            <Card className="overflow-hidden p-0">
              <GraphCanvas
                graph={graph}
                exercises={exerciseById}
                selection={selection}
                onSelect={setSelection}
                onMove={choreography.moveState}
                onOpen={openInEditor}
                run={run}
                onSignal={control.signal}
                onGoto={control.goto}
              />
            </Card>
            {run ? (
              <RunPanel graph={graph} run={run} sending={control.sending} onSignal={control.signal} onStop={control.stop} />
            ) : (
              <GraphInspector
                graph={graph}
                selection={selection}
                exercises={exerciseById}
                onRename={choreography.renameState}
                onRenameTransition={choreography.renameTransition}
                onOpen={openInEditor}
                onSetInitial={choreography.setInitialState}
                onRemove={(stateId) => setToRemove(graph.states.find((s) => s.state_id === stateId) ?? null)}
              />
            )}
          </div>
        </div>
      )}

      <ConfirmDialog
        open={toRemove !== null}
        onOpenChange={(open) => { if (!open) setToRemove(null); }}
        title="Odstrániť stav z choreografie?"
        description={`Stav „${toRemove?.label}“ a jeho prechody sa odstránia z choreografie. Cvičenie zostane.`}
        confirmLabel="Odstrániť"
        onConfirm={() => {
          if (!toRemove) return;
          choreography.removeState(toRemove.state_id);
          setSelection(null);
        }}
      />
    </Page>
  );
}
