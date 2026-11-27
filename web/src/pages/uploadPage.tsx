import { useState } from "react";
import { Page } from "@/components/layout/page";
import { StatusAlert } from "@/components/ui/statusAlert";
import { MediaUpload } from "@/components/exercise/mediaUpload";
import { useStatus } from "@/hooks/useStatus";
import { failureText } from "@/lib/errors";
import { createExerciseFromImage, createExerciseFromVideo, nameFromFile } from "@/lib/exercises";
import type { VideoRange } from "@/lib/videoRange";

export default function UploadPage() {
  const [uploading, setUploading] = useState(false);
  const { status, show: showStatus, clear: clearStatus } = useStatus();

  // whole video at one frame per second, image as single frame
  const create = async (file: File, range: VideoRange | null) => {
    setUploading(true);
    clearStatus();
    const name = nameFromFile(file);
    try {
      if (file.type.startsWith("video/")) await createExerciseFromVideo(file, range, { name, fps: 1, seconds: -1 });
      else await createExerciseFromImage(file, name);
      showStatus("success", `Cvičenie „${name}“ bolo vytvorené.`);
      return true;
    } catch (err) {
      showStatus("error", failureText("Nahranie zlyhalo", err));
      return false;
    } finally {
      setUploading(false);
    }
  };

  return (
    <Page title="Nahranie" description="Nahrajte video alebo obrázok a vytvorte z neho cvičenie.">
      <StatusAlert status={status} />
      <MediaUpload
        accept="video/*,image/*"
        formats="MP4, MOV, AVI, WEBM, JPG, PNG"
        submitLabel={uploading ? "Nahrávanie…" : "Vytvoriť cvičenie"}
        submitting={uploading}
        onSubmit={create}
        onSelect={clearStatus}
        onClear={clearStatus}
        onReject={() => showStatus("error", "Vyberte video alebo obrázok.")}
      />
    </Page>
  );
}
