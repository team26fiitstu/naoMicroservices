import { useState } from "react";
import { ArrowLeftRight, ArrowRight, ArrowUpRight, Copy, Film, Flag, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { MetaItem, MetaRow } from "@/components/ui/meta";
import { NameInput } from "@/components/ui/nameInput";
import { ExerciseSelect } from "@/components/exercise/exerciseSelect";
import { EXERCISE_SOURCES } from "@/components/exercise/exerciseSources";
import { stateLabel, type Choreography, type GraphSelection } from "@/lib/choreography";
import { exerciseDisplayName } from "@/lib/exerciseName";
import type { ExerciseSummary } from "@/lib/exercises";
import { pluralSk } from "@/lib/plural";

type Props = {
  graph: Choreography;
  selection: GraphSelection;
  exercises: Map<string, ExerciseSummary>;
  onRename: (stateId: string, label: string) => Promise<boolean>;
  onRenameTransition: (transitionId: string, label: string) => Promise<boolean>;
  onOpen: (stateId: string) => void;
  onSetInitial: (stateId: string) => void;
  // label, position and transitions stay
  onChangeExercise: (stateId: string, exerciseId: string) => void;
  onDuplicate: (stateId: string) => void;
  onRemove: (stateId: string) => void;
};

// side panel with everything about selected state or transition, graph shows only labels
export function GraphInspector({ graph, selection, exercises, onRename, onRenameTransition, onOpen, onSetInitial, onChangeExercise, onDuplicate, onRemove }: Props) {
  // id of state with open exercise picker, other selected state closes it
  const [changing, setChanging] = useState<string | null>(null);
  const state = selection?.kind === "state" ? graph.states.find((s) => s.id === selection.id) : undefined;
  const transition = selection?.kind === "transition" ? graph.transitions.find((t) => t.id === selection.id) : undefined;

  if (state) {
    const exercise = exercises.get(state.exercise_id);
    const source = exercise && EXERCISE_SOURCES[exercise.source];
    const initial = state.id === graph.initial_state;
    return (
      // name, facts and actions as three blocks
      <Card className="gap-5 px-5 py-4">
        <NameInput name={state.label} label="Názov stavu" onRename={(label) => onRename(state.id, label)} />
        <div className="space-y-1.5">
          {exercise && (
            // exercise behind state, same exercise may be in several states
            <button
              type="button"
              onClick={() => onOpen(state.id)}
              title="Otvoriť cvičenie v editore"
              className="flex max-w-full items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground hover:underline"
            >
              <ArrowUpRight className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{exerciseDisplayName(exercise.name)}</span>
            </button>
          )}
          <MetaRow>
            {source && <MetaItem icon={source.icon}>{source.label}</MetaItem>}
            {exercise?.source === "video" && <MetaItem icon={Film}>{exercise.frame_count} {pluralSk(exercise.frame_count, "snímka", "snímky", "snímok")}</MetaItem>}
            {initial && <MetaItem icon={Flag}>Počiatočný</MetaItem>}
          </MetaRow>
        </div>
        <div className="flex flex-col gap-2">
          <Button size="sm" variant="outline" onClick={() => onSetInitial(state.id)} disabled={initial}>
            <Flag className="h-3.5 w-3.5" />
            Nastaviť ako počiatočný
          </Button>
          <Button size="sm" variant={changing === state.id ? "secondary" : "outline"} onClick={() => setChanging(changing === state.id ? null : state.id)}>
            <ArrowLeftRight className="h-3.5 w-3.5" />
            Zmeniť cvičenie
          </Button>
          {changing === state.id && (
            <ExerciseSelect
              exercises={[...exercises.values()]}
              value={state.exercise_id}
              onValueChange={(exerciseId) => {
                setChanging(null);
                if (exerciseId !== state.exercise_id) onChangeExercise(state.id, exerciseId);
              }}
              placeholder="Vyberte cvičenie…"
              emptyText="Zatiaľ žiadne cvičenia"
            />
          )}
          <Button size="sm" variant="outline" onClick={() => onDuplicate(state.id)}>
            <Copy className="h-3.5 w-3.5" />
            Duplikovať
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onRemove(state.id)}
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
