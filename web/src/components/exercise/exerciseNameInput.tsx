import { NameInput } from "@/components/ui/nameInput";
import { DEFAULT_EXERCISE_NAME, exerciseDisplayName } from "@/lib/exerciseName";

type Props = {
  name: string;
  // resolves false when the name was not saved
  onRename: (name: string) => Promise<boolean>;
  className?: string;
};

// Exercise name, unnamed exercises show default name
export function ExerciseNameInput({ name, onRename, className }: Props) {
  return (
    <NameInput
      name={exerciseDisplayName(name)}
      label="Názov cvičenia"
      placeholder={DEFAULT_EXERCISE_NAME}
      onRename={onRename}
      className={className}
    />
  );
}
