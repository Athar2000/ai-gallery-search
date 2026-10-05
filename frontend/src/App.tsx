import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DashboardPage from "./pages/DashboardPage";
import PeoplePage from "./pages/PeoplePage";
import PhotosPage from "./pages/PhotosPage";
import PhotoDetailPage from "./pages/PhotoDetailPage";
import SearchResultsPage from "./pages/SearchResultsPage";
import AlbumsPage from "./pages/AlbumsPage";
import LocationsPage from "./pages/LocationsPage";
import TimelinePage from "./pages/TimelinePage";
import SettingsPage from "./pages/SettingsPage";
import SmartFiltersPage from "./pages/SmartFiltersPage";
import { AppShell } from "./components/AppShell";

function Protected({ children }: { children: React.ReactNode }) {
  return <ProtectedRoute><AppShell>{children}</AppShell></ProtectedRoute>;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/" element={<Protected><DashboardPage /></Protected>} />
          <Route path="/photos" element={<Protected><PhotosPage /></Protected>} />
          <Route path="/photos/:id" element={<Protected><PhotoDetailPage /></Protected>} />
          <Route path="/search" element={<Protected><SearchResultsPage /></Protected>} />
          <Route path="/people" element={<Protected><PeoplePage /></Protected>} />
          <Route path="/albums" element={<Protected><AlbumsPage /></Protected>} />
          <Route path="/locations" element={<Protected><LocationsPage /></Protected>} />
          <Route path="/timeline" element={<Protected><TimelinePage /></Protected>} />
          <Route path="/settings" element={<Protected><SettingsPage /></Protected>} />
          <Route path="/smart-filters" element={<Protected><SmartFiltersPage /></Protected>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
