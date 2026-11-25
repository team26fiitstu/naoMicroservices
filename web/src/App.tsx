import { Routes, Route, Navigate } from "react-router-dom";
import MainPage from "./pages/mainPage";
import VideoEditor from "./pages/videoEditor";
import ExercisesStore from "./pages/exercisesStore";
import SimpleUploadPage from "./pages/simpleUploadPage";
import VoiceCommandPage from "./pages/voiceCommandPage";
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
          <Route path="/exercises" element={<ExercisesStore />} />
          <Route path="/edit" element={<VideoEditor />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
      <BottomNav />
    </div>
  );
}

export default App;
