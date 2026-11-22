import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type Props = {
  onFile: (file: File) => void;
  onReject: () => void;
  accept: string;
  formats: string;
};

// "video/*,image/*" style check; drag and drop bypasses the input accept filter
const accepts = (file: File, accept: string) =>
  accept.split(",").some((type) => (type.endsWith("/*") ? file.type.startsWith(type.slice(0, -1)) : file.type === type));

// Drop or click to pick file
export function FileDropzone({ onFile, onReject, accept, formats }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const pick = (file?: File) => {
    if (!file) return;
    if (accepts(file, accept)) onFile(file);
    else onReject();
  };

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
        pick(e.dataTransfer.files[0]);
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
          pick(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
    </Card>
  );
}
