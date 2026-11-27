import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import MainPage from "@/pages/mainPage";
import EditorPage from "@/pages/editorPage";
import ExercisesPage from "@/pages/exercisesPage";
import UploadPage from "@/pages/uploadPage";
import VoicePage from "@/pages/voicePage";
import { SideNav } from "@/components/layout/sideNav";
import { BottomNav } from "@/components/layout/bottomNav";

// graph pages bring React Flow, loaded only when opened
const ChoreographiesPage = lazy(() => import("@/pages/choreographiesPage"));
const ChoreographyPage = lazy(() => import("@/pages/choreographyPage"));

function App() {
  return (
    <div className="min-h-screen flex">
      <SideNav />
      <div className="flex-1 flex flex-col min-w-0">
        <Suspense>
          <Routes>
            <Route path="/" element={<MainPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/voice" element={<VoicePage />} />
            <Route path="/exercises" element={<ExercisesPage />} />
            <Route path="/edit" element={<EditorPage />} />
            <Route path="/choreographies" element={<ChoreographiesPage />} />
            <Route path="/choreographies/:id" element={<ChoreographyPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </div>
      <BottomNav />
    </div>
  );
}

export default App;
