import { VoiceCommander } from "@/components/voice/voiceCommander";
import { AiBadge } from "@/components/voice/aiBadge";
import { PageHeader } from "@/components/layout/pageHeader";

export default function VoicePage() {
  return (
    <div className="w-full max-w-7xl mx-auto px-4 py-6 pb-24 space-y-4">
      <PageHeader
        title="Hlasové príkazy"
        description={<span className="flex items-center gap-2">Povedzte názov pózy a robot ju vykoná. <AiBadge /></span>}
      />
      <VoiceCommander />
    </div>
  );
}
