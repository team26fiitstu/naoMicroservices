import { Bot, Image, Video, type LucideIcon } from "lucide-react";
import type { ExerciseSource } from "@/lib/exercises";

// Label and icon of what exercise was built from
export const EXERCISE_SOURCES: Record<ExerciseSource, { label: string; icon: LucideIcon }> = {
  video: { label: "Video", icon: Video },
  image: { label: "Obrázok", icon: Image },
  poses: { label: "Príkazy", icon: Bot },
};
