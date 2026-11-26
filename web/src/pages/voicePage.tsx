import { VoiceCommander } from "@/components/voice/voiceCommander";
import { AiBadge } from "@/components/voice/aiBadge";
import { Page } from "@/components/layout/page";

export default function VoicePage() {
  return (
    <Page
      title="Hlasové príkazy"
      description={<span className="flex items-center gap-2">Povedzte názov pózy a robot ju vykoná. <AiBadge /></span>}
    >
      <VoiceCommander />
    </Page>
  );
}
