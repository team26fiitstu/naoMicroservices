import { Flame, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ExerciseNameInput } from "@/components/exercise/exerciseNameInput";

type Props = {
  name: string;
  onRename: (name: string) => Promise<boolean>;
  calories: number | null;
  caloriesLoading: boolean;
  description: string | null;
  descLoading: boolean;
};

// Exercise name with AI calorie estimate and description
export function ExerciseInfo({ name, onRename, calories, caloriesLoading, description, descLoading }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <ExerciseNameInput name={name} onRename={onRename} className="w-64" />
        {caloriesLoading ? (
          <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Odhadovanie kalórií…
          </span>
        ) : calories != null ? (
          <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <Flame className="h-3.5 w-3.5" />
            {calories} kcal
            <Badge variant="secondary" className="px-1.5 py-0 text-[10px] font-normal">Odhad AI</Badge>
          </span>
        ) : null}
      </div>
      {descLoading ? (
        <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Generovanie popisu pomocou AI…
        </span>
      ) : description ? (
        <p className="max-w-3xl text-xs leading-relaxed text-muted-foreground">{description}</p>
      ) : null}
    </div>
  );
}
