import { useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { DEFAULT_EXERCISE_NAME, exerciseDisplayName } from "@/lib/exerciseName";

type Props = {
  name: string;
  onRename: (name: string) => void;
  className?: string;
};

// Always-visible name field: Enter or blur saves, Escape or empty restores
export function ExerciseNameInput({ name, onRename, className }: Props) {
  const savedName = exerciseDisplayName(name);
  const [draft, setDraft] = useState(savedName);
  const [shownName, setShownName] = useState(savedName);
  const cancelled = useRef(false);

  // saved name changed outside, show it
  if (shownName !== savedName) {
    setShownName(savedName);
    setDraft(savedName);
  }

  return (
    <Input
      aria-label="Názov cvičenia"
      placeholder={DEFAULT_EXERCISE_NAME}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => {
        const next = draft.trim();
        if (!cancelled.current && next && next !== savedName) onRename(next);
        else setDraft(savedName);
        cancelled.current = false;
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") cancelled.current = true;
        if (e.key === "Enter" || e.key === "Escape") e.currentTarget.blur();
      }}
      className={cn("font-medium placeholder:font-normal hover:border-ring/60", className)}
    />
  );
}
