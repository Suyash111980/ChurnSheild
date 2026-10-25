import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { supabase } from "../lib/supabase";
import { apiRequest } from "../services/apiClient";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [accountProfile, setAccountProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileErrorStatus, setProfileErrorStatus] = useState(null);
  const [profileErrorDetail, setProfileErrorDetail] = useState(null);
  const [authFlowInProgress, setAuthFlowInProgress] = useState(false);
  const [authIntroIntent, setAuthIntroIntent] = useState(null);
  const [passwordRecovery, setPasswordRecovery] = useState(() => {
    try { return window.sessionStorage.getItem("churnshield-password-recovery") === "true"; }
    catch { return false; }
  });

  const refreshAccountProfile = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setProfileLoading(true);
    setProfileErrorStatus(null);
    setProfileErrorDetail(null);
    try {
      const profile = await apiRequest("/auth/status");
      setAccountProfile(profile);
      return profile;
    } catch (error) {
      setAccountProfile(null);
      setProfileErrorStatus(Number.isInteger(error?.status) ? error.status : null);
      setProfileErrorDetail(typeof error?.detail === "string" ? error.detail : null);
      throw error;
    } finally {
      if (!silent) setProfileLoading(false);
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    let profileLoadId = 0;

    async function initializeSession() {
      const { data, error } = await supabase.auth.getSession();
      if (!mounted) return;

      const session = error ? null : data.session;
      setUser(session?.user ?? null);
      let loadId = profileLoadId;
      if (session) {
        loadId = ++profileLoadId;
        try {
          const profile = await apiRequest("/auth/status");
          if (mounted && loadId === profileLoadId) {
            setAccountProfile(profile);
            setProfileErrorStatus(null);
            setProfileErrorDetail(null);
          }
        } catch (profileError) {
          if (mounted && loadId === profileLoadId) {
            setAccountProfile(null);
            setProfileErrorStatus(Number.isInteger(profileError?.status) ? profileError.status : null);
            setProfileErrorDetail(typeof profileError?.detail === "string" ? profileError.detail : null);
          }
        }
      } else {
        profileLoadId += 1;
        setAccountProfile(null);
        setProfileErrorStatus(null);
        setProfileErrorDetail(null);
      }
      if (mounted && (!session || loadId === profileLoadId)) setProfileLoading(false);
      setLoading(false);
    }

    void initializeSession();

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (!mounted) return;
      setUser(session?.user ?? null);
      if (event === "PASSWORD_RECOVERY") {
        setPasswordRecovery(true);
        try { window.sessionStorage.setItem("churnshield-password-recovery", "true"); } catch { /* Recovery remains available for this mount. */ }
      } else if (event === "SIGNED_IN") {
        setPasswordRecovery(false);
        try { window.sessionStorage.removeItem("churnshield-password-recovery"); } catch { /* Ignore unavailable storage. */ }
      }
      if (!session) {
        setPasswordRecovery(false);
        try { window.sessionStorage.removeItem("churnshield-password-recovery"); } catch { /* Ignore unavailable storage. */ }
        profileLoadId += 1;
        setAccountProfile(null);
        setProfileErrorStatus(null);
        setProfileErrorDetail(null);
        setProfileLoading(false);
      } else if (event === "SIGNED_IN") {
        const loadId = ++profileLoadId;
        setProfileLoading(true);
        // Resolve the trusted backend role for restored or externally initiated sessions too.
        Promise.resolve().then(async () => {
          try {
            const profile = await apiRequest("/auth/status");
            if (mounted && loadId === profileLoadId) {
              setAccountProfile(profile);
              setProfileErrorStatus(null);
              setProfileErrorDetail(null);
            }
          } catch (profileError) {
            if (mounted && loadId === profileLoadId) {
              setAccountProfile(null);
              setProfileErrorStatus(Number.isInteger(profileError?.status) ? profileError.status : null);
              setProfileErrorDetail(typeof profileError?.detail === "string" ? profileError.detail : null);
            }
          } finally {
            if (mounted && loadId === profileLoadId) setProfileLoading(false);
          }
        });
      }
      setLoading(false);
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, []);

  async function signup({ name, email, password, requestAdmin = false }) {
    setAuthIntroIntent(null);
    setAuthFlowInProgress(true);
    try {
      const { data, error } = await supabase.auth.signUp({
        email: email.trim().toLowerCase(),
        password,
        options: {
          data: {
            full_name: name.trim(),
            ...(requestAdmin ? { requested_role: "admin" } : {}),
          },
        },
      });
      if (error) throw error;
      if (data.session) {
        // Supabase signup succeeded even if the separate backend profile lookup is unavailable.
        // Keep the session and let AccountStatus show the stored API/configuration error.
        try { await refreshAccountProfile(); } catch { /* refreshAccountProfile stores the error state */ }
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
      // Do not report a successful Supabase sign-in as a credential failure when only
      // the backend's profile/status service is unavailable.
      try { await refreshAccountProfile(); } catch { /* refreshAccountProfile stores the error state */ }
      setAuthIntroIntent("login");
      return data;
    } finally {
      setAuthFlowInProgress(false);
    }
  }

  const consumeAuthIntro = useCallback(() => setAuthIntroIntent(null), []);
  const clearPasswordRecovery = useCallback(() => {
    setPasswordRecovery(false);
    try { window.sessionStorage.removeItem("churnshield-password-recovery"); } catch { /* Ignore unavailable storage. */ }
  }, []);

  async function logout() {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
  }

  return (
    <AuthContext.Provider value={{
      user,
      accountProfile,
      profileErrorStatus,
      profileErrorDetail,
      refreshAccountProfile,
      loading,
      profileLoading,
      authFlowInProgress,
      authIntroIntent,
      passwordRecovery,
      clearPasswordRecovery,
      consumeAuthIntro,
      isAuthenticated: Boolean(user),
      signup,
      login,
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
