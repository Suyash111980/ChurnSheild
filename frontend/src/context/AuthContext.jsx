
import {
  createContext,
  useContext,
  useEffect,
  useCallback,
  useState,
} from "react";
import { supabase } from "../lib/supabase";
import { apiRequest } from "../services/apiClient";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [accountProfile, setAccountProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [authFlowInProgress, setAuthFlowInProgress] = useState(false);
  const [authIntroIntent, setAuthIntroIntent] = useState(null);

  const refreshAccountProfile = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setProfileLoading(true);
    try {
      const profile = await apiRequest("/auth/status");
      setAccountProfile(profile);
      return profile;
    } finally {
      if (!silent) setProfileLoading(false);
    }
  }, []);

  useEffect(() => {
    let mounted = true;

    async function initializeSession() {
      const { data, error } = await supabase.auth.getSession();

      if (!mounted) return;

      const session = error ? null : data.session;
      setUser(session?.user ?? null);
      if (session) {
        try {
          const profile = await apiRequest("/auth/status");
          if (mounted) setAccountProfile(profile);
        } catch {
          if (mounted) setAccountProfile(null);
        }
      } else {
        setAccountProfile(null);
      }
      if (mounted) setProfileLoading(false);
      setLoading(false);
    }

    initializeSession();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (mounted) {
        setUser(session?.user ?? null);
        if (!session) {
          setAccountProfile(null);
          setProfileLoading(false);
        } else if (_event === "SIGNED_IN") {
          setProfileLoading(true);
        }
        setLoading(false);
      }
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, []);

  async function signup({ name, email, password }) {
    setAuthIntroIntent(null);
    setAuthFlowInProgress(true);
    try {
      const { data, error } = await supabase.auth.signUp({
        email: email.trim().toLowerCase(),
        password,
        options: {
          data: { full_name: name.trim() },
        },
      });

      if (error) throw error;
      if (data.session) {
        await refreshAccountProfile();
        setAuthIntroIntent("signup");
      }
      return data;
    } finally {
      setAuthFlowInProgress(false);
    }
  }

  async function login(email, password) {
    setAuthIntroIntent(null);
    setAuthFlowInProgress(true);

    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email: email.trim().toLowerCase(),
        password,
      });

      if (error) throw error;
      await refreshAccountProfile();
      // One-shot UI handoff for a confirmed login; authorization is still enforced by ProtectedRoute.
      setAuthIntroIntent("login");
      return data;
    } finally {
      setAuthFlowInProgress(false);
    }
  }

  const consumeAuthIntro = useCallback(() => setAuthIntroIntent(null), []);

  async function logout() {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        accountProfile,
        refreshAccountProfile,
        loading,
        profileLoading,
        authFlowInProgress,
        authIntroIntent,
        consumeAuthIntro,
        isAuthenticated: Boolean(user),
        signup,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }

  return context;
}
