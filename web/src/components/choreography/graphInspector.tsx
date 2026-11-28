import { ArrowRight, Film, Flag, FolderOpen, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ExerciseNameInput } from "@/components/exercise/exerciseNameInput";
import { MetaItem, MetaRow } from "@/components/ui/meta";
import { NameInput } from "@/components/ui/nameInput";
import { EXERCISE_SOURCES } from "@/components/exercise/exerciseSources";
import { stateLabel, type Choreography, type GraphSelection } from "@/lib/choreography";
import type { ExerciseSummary } from "@/lib/exercises";
import { pluralSk } from "@/lib/plural";

type Props = {
  graph: Choreography;
  selection: GraphSelection;
  exercises: Map<string, ExerciseSummary>;
  // renames exercise, state label follows
  onRename: (stateId: string, name: string) => Promise<boolean>;
  onRenameTransition: (transitionId: string, label: string) => Promise<boolean>;
  onOpen: (stateId: string) => void;
  onSetInitial: (stateId: string) => void;
  onRemove: (stateId: string) => void;
};

// side panel with everything about selected state or transition, graph shows only labels
export function GraphInspector({ graph, selection, exercises, onRename, onRenameTransition, onOpen, onSetInitial, onRemove }: Props) {
  const state = selection?.kind === "state" ? graph.states.find((s) => s.state_id === selection.id) : undefined;
  const transition = selection?.kind === "transition" ? graph.transitions.find((t) => t.id === selection.id) : undefined;

  if (state) {
    const exercise = exercises.get(state.state_id);
    const source = exercise && EXERCISE_SOURCES[exercise.source];
    const initial = state.state_id === graph.initial_state;
    return (
      <Card className="gap-4 px-5 py-4">
        <div className="space-y-2">
          <ExerciseNameInput name={exercise?.name ?? state.label} onRename={(name) => onRename(state.state_id, name)} />
          <MetaRow>
            {source && <MetaItem icon={source.icon}>{source.label}</MetaItem>}
            {exercise?.source === "video" && <MetaItem icon={Film}>{exercise.frame_count} {pluralSk(exercise.frame_count, "snímka", "snímky", "snímok")}</MetaItem>}
            {initial && <MetaItem icon={Flag}>Počiatočný</MetaItem>}
          </MetaRow>
        </div>
        <div className="flex flex-col gap-2">
          <Button size="sm" variant="outline" onClick={() => onOpen(state.state_id)}>
            <FolderOpen className="h-3.5 w-3.5" />
            Otvoriť v editore
          </Button>
          <Button size="sm" variant="outline" onClick={() => onSetInitial(state.state_id)} disabled={initial}>
            <Flag className="h-3.5 w-3.5" />
            Nastaviť ako počiatočný
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onRemove(state.state_id)}
            disabled={initial}
            title={initial ? "Počiatočný stav nemožno odstrániť" : undefined}
            className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Odstrániť z choreografie
          </Button>
        </div>
      </Card>
    );
  }

  if (transition) {
    return (
      <Card className="gap-2 px-5 py-4">
        <NameInput name={transition.label} label="Názov prechodu" onRename={(label) => onRenameTransition(transition.id, label)} />
        <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          {stateLabel(graph, transition.from)}
          <ArrowRight className="h-3.5 w-3.5" />
          {stateLabel(graph, transition.to)}
        </p>
      </Card>
    );
  }

  return (
    <Card className="px-5 py-4 text-xs leading-relaxed text-muted-foreground">
      Kliknite na stav alebo prechod pre detail. Dvojklik na stav ho otvorí v editore.
    </Card>
  );
}
