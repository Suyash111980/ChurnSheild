
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import AppLayout from "./components/layout/AppLayout";
import Analytics from "./pages/Analytics";
import Dashboard from "./pages/Dashboard";
import Learners from "./pages/Learners";
import LearnerProfile from "./pages/LearnerProfile";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Settings from "./pages/Settings";
import Signup from "./pages/Signup";
import AccountStatus from "./pages/AccountStatus";
import AdminApprovals from "./pages/AdminApprovals";
import DatasetImport from "./pages/DatasetImport";
import EarlyWarning from "./pages/EarlyWarning";
import Recommendations from "./pages/Recommendations";
import Reports from "./pages/Reports";
import RootCause from "./pages/RootCause";
import CourseInsights from "./pages/CourseInsights";
import MasterAdminDashboard from "./pages/MasterAdminDashboard";
import OuladOverview from "./pages/OuladOverview";
import { roleRedirect } from "./utils/roleNavigation";

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading, accountProfile, profileLoading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="auth-loading" role="status">
        Checking session...
      </div>
    );
  }

  if (isAuthenticated && profileLoading) {
    return <div className="auth-loading" role="status">Checking account approval...</div>;
  }

  if (isAuthenticated && accountProfile?.approval_status !== "approved") {
    return <Navigate to="/account-status" replace />;
  }

  const roleTarget = isAuthenticated && accountProfile?.approval_status === "approved"
    ? roleRedirect(accountProfile.app_role, location.pathname)
    : null;
  if (roleTarget) return <Navigate to={roleTarget} replace />;

  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function MasterOnly({ children }) {
  const { accountProfile } = useAuth();
  return accountProfile?.app_role === "master_admin" ? children : <Navigate to="/dashboard" replace />;
}

function GuestRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="auth-loading" role="status">
        Checking session...
      </div>
    );
  }

  return isAuthenticated ? <Navigate to="/dashboard" replace /> : children;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />

        <Route
          path="/login"
          element={
            <GuestRoute>
              <Login />
            </GuestRoute>
          }
        />

        <Route
          path="/signup"
          element={
            <GuestRoute>
              <Signup />
            </GuestRoute>
          }
        />

        <Route path="/account-status" element={<AccountStatus />} />

        <Route
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/datasets" element={<DatasetImport />} />
          <Route path="/learners" element={<Learners />} />
          <Route path="/learners/:learnerId" element={<LearnerProfile />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/early-warning" element={<EarlyWarning />} />
          <Route path="/root-cause" element={<RootCause />} />
          <Route path="/recommendations" element={<Recommendations />} />
          <Route path="/course-insights" element={<CourseInsights />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/admin/users" element={<AdminApprovals />} />
          <Route path="/master-admin" element={<MasterOnly><MasterAdminDashboard /></MasterOnly>} />
          <Route path="/master-admin/oulad" element={<MasterOnly><OuladOverview /></MasterOnly>} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </AuthProvider>
  );
}
