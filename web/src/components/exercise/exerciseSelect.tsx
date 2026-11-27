import { Select } from "@/components/ui/select";
import { exerciseDisplayName } from "@/lib/exerciseName";
import type { ExerciseSummary } from "@/lib/exercises";

type Props = {
  exercises: ExerciseSummary[];
  value: string;
  onValueChange: (id: string) => void;
  placeholder: string;
  // shown instead of placeholder when there is nothing to choose
  emptyText: string;
  className?: string;
};

// Saved exercise picker by display name
export function ExerciseSelect({ exercises, value, onValueChange, placeholder, emptyText, className }: Props) {
  return (
    <Select
      className={className}
      label="Cvičenie"
      placeholder={exercises.length ? placeholder : emptyText}
      value={value}
      onValueChange={onValueChange}
      options={exercises.map((e) => ({ value: e.id, label: exerciseDisplayName(e.name) }))}
      disabled={exercises.length === 0}
    />
  );
}
