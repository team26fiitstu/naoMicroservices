import { useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";

type Props = {
  name: string;
  label: string;
  placeholder?: string;
  // resolves false when the name was not saved
  onRename: (name: string) => Promise<boolean>;
  className?: string;
};

// Always-visible name field: Enter or blur saves, Escape, empty name or failed save restores
export function NameInput({ name, label, placeholder, onRename, className }: Props) {
  const [draft, setDraft] = useState(name);
  const [shownName, setShownName] = useState(name);
  const cancelled = useRef(false);

  // saved name changed outside, show it
  if (shownName !== name) {
    setShownName(name);
    setDraft(name);
  }

  return (
    <Input
      aria-label={label}
      placeholder={placeholder}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={async () => {
        const next = draft.trim();
        const cancel = cancelled.current;
        cancelled.current = false;
        if (cancel || !next || next === name || !(await onRename(next))) setDraft(name);
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") cancelled.current = true;
        if (e.key === "Enter" || e.key === "Escape") e.currentTarget.blur();
      }}
      className={cn("font-medium placeholder:font-normal hover:border-ring/60", className)}
    />
  );
}
