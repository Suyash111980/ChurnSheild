
import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
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
import {
  CourseInsights,
  EarlyWarning,
  Recommendations,
  Reports,
  RootCause,
} from "./pages/WorkspacePages";

function ProtectedRoute({ children }) {
  const {
    isAuthenticated,
    loading,
    accountProfile,
    profileLoading,
    authFlowInProgress,
    authIntroIntent,
    consumeAuthIntro,
  } = useAuth();

  // Consume the one-shot intent whether approval succeeds or redirects to account status.
  useEffect(() => {
    if (isAuthenticated && !loading && !profileLoading && !authFlowInProgress && authIntroIntent) {
      consumeAuthIntro();
    }
  }, [isAuthenticated, loading, profileLoading, authFlowInProgress, authIntroIntent, consumeAuthIntro]);

  if (loading) {
    return (
      <div className="auth-loading" role="status">
        Checking session...
      </div>
    );
  }

  if (isAuthenticated && profileLoading) {
    return <AccountStatus />;
  }

  if (isAuthenticated && accountProfile?.approval_status !== "approved") {
    return <Navigate to="/account-status" replace />;
  }

  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function GuestRoute({ children }) {
  const { isAuthenticated, loading, profileLoading, authFlowInProgress, authIntroIntent } = useAuth();

  if (loading) {
    return (
      <div className="auth-loading" role="status">
        Checking session...
      </div>
    );
  }

  // Keep the guest view mounted until a sign-in/sign-up flow and its profile check resolve.
  // This lets the correct one-shot intro intent arrive before the guest redirect.
  if (isAuthenticated && (profileLoading || authFlowInProgress)) return children;

  return isAuthenticated ? (
    <Navigate
      to="/dashboard"
      replace
      state={authIntroIntent ? { showLoginIntro: true, introSize: authIntroIntent } : undefined}
    />
  ) : children;
}

export default function App() {
  return (
    <ThemeProvider>
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
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </AuthProvider>
    </ThemeProvider>
  );
}
