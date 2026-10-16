import { Routes, Route } from "react-router-dom";
import MainPage from "./pages/mainPage";
import ExercisePage from "./pages/exercisePage";
import VideoEditor from "./pages/videoEditor";
import GroupPage from "./pages/groupPage";
import ExercisesStore from "./pages/exercisesStore";
import SimpleUploadPage from "./pages/simpleUploadPage";
import VoiceCommandPage from "./pages/voiceCommandPage";
import AudioRecorderAggregatorPage from "./pages/audioRecorderAggregatorPage";
import { SideNav } from "./components/layout/sideNav";
import { BottomNav } from "./components/layout/bottomNav";

function App() {
  return (
    <div className="min-h-screen flex">
      <SideNav />
      <div className="flex-1 flex flex-col min-w-0">
        <Routes>
          <Route path="/" element={<MainPage />} />
          <Route path="/upload" element={<SimpleUploadPage />} />
          <Route path="/voice" element={<VoiceCommandPage />} />
          <Route path="/exercise" element={<ExercisePage />} />
          <Route path="/exercises" element={<ExercisesStore />} />
          <Route path="/group" element={<GroupPage />} />
          <Route path="/edit" element={<VideoEditor />} />
          <Route path="/record" element={<AudioRecorderAggregatorPage />} />
        </Routes>
      </div>
      <BottomNav />
    </div>
  );
}

export default App;
