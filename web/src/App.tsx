import { Routes, Route, Navigate } from "react-router-dom";
import MainPage from "@/pages/mainPage";
import EditorPage from "@/pages/editorPage";
import ExercisesPage from "@/pages/exercisesPage";
import UploadPage from "@/pages/uploadPage";
import VoicePage from "@/pages/voicePage";
import { SideNav } from "@/components/layout/sideNav";
import { BottomNav } from "@/components/layout/bottomNav";

function App() {
  return (
    <div className="min-h-screen flex">
      <SideNav />
      <div className="flex-1 flex flex-col min-w-0">
        <Routes>
          <Route path="/" element={<MainPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/voice" element={<VoicePage />} />
          <Route path="/exercises" element={<ExercisesPage />} />
          <Route path="/edit" element={<EditorPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
      <BottomNav />
    </div>
  );
}

export default App;
