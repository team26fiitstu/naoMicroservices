import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type Props = {
  onFile: (file: File) => void;
  accept: string;
  formats: string;
};

// Drop or click to pick file
export function FileDropzone({ onFile, accept, formats }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  return (
    <Card
      className={cn(
        "border-2 border-dashed cursor-pointer transition-colors duration-200",
        dragging ? "border-primary bg-muted/40" : "hover:border-primary/50 hover:bg-muted/30",
      )}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      // ignore leave events from child elements
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false); }}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const file = e.dataTransfer.files[0];
        if (file) onFile(file);
      }}
    >
      <div className="flex flex-col items-center justify-center gap-3 py-14 px-8 text-center">
        <Upload className="h-6 w-6 text-muted-foreground" />
        <div>
          <p className="text-sm font-medium text-foreground">Presuňte sem</p>
          <p className="text-xs text-muted-foreground mt-0.5">alebo kliknite pre výber</p>
        </div>
        <Badge variant="secondary" className="text-xs">{formats}</Badge>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
          e.target.value = "";
        }}
      />
    </Card>
  );
}
