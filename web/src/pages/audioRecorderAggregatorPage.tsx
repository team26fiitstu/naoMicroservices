import { AudioRecorderComponent } from "@/components/ui/audioRecorder";

export default function AudioRecorderAggregatorPage() {
  const [overallRecordedMessage, onOverallRecordedMessageChange] = useState({});
  return (
    <div className="w-full max-w-xl mx-auto px-4 py-6 pb-24 space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Hlášky robota</h1>
        <p className="text-xs text-muted-foreground mt-0.5">Povedzte čo NAO má povedať.</p>
      </div>
      <AudioRecorderComponent saveAudioFile={(audio, audioFormat) => {}} overallRecordedMessage={recordedMessages} onOverallRecordedMessageChange={onOverallRecordedMessageChange}/>
    </div>
  );
}