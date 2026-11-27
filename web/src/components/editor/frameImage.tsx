import { useState } from "react";
import { Film } from "lucide-react";
import { API_BASE } from "@/lib/api";
import type { Frame } from "@/lib/frames";

// Frame photo, then pose image, then placeholder
export function FrameImage({ frame, exerciseId, className }: { frame: Frame; exerciseId: string; className: string }) {
  const sources = [
    `${API_BASE}/exercise/${exerciseId}/frame/${frame.idx}/image`,
    frame.pose_name ? `${API_BASE}/pose/${frame.pose_name}/image` : null,
  ].filter((src): src is string => src !== null);
  const [failed, setFailed] = useState(0);

  if (failed >= sources.length) {
    return (
      <div className={`${className} rounded-base bg-muted flex items-center justify-center`}>
        <Film className="h-5 w-5 text-muted-foreground opacity-40" />
      </div>
    );
  }
  return (
    <img
      src={sources[failed]}
      alt={frame.pose_name ?? `Snímka ${frame.idx}`}
      className={`${className} rounded-base bg-muted`}
      onError={() => setFailed((n) => n + 1)}
    />
  );
}
