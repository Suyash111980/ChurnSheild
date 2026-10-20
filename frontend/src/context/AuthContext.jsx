
import {
  createContext,
  useContext,
  useEffect,
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
  const [profileErrorStatus, setProfileErrorStatus] = useState(null);
  const [profileErrorDetail, setProfileErrorDetail] = useState(null);

  async function refreshAccountProfile() {
    setProfileLoading(true);
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
      setProfileLoading(false);
    }
  }

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

    initializeSession();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (mounted) {
        setUser(session?.user ?? null);
        if (!session) {
          profileLoadId += 1;
          setAccountProfile(null);
          setProfileErrorStatus(null);
          setProfileErrorDetail(null);
          setProfileLoading(false);
        } else if (_event === "SIGNED_IN") {
          const loadId = ++profileLoadId;
          setProfileLoading(true);
          // Supabase can emit SIGNED_IN outside login() (for example after
          // session restoration). Resolve the trusted backend role in that
          // path too, or protected routes remain stuck with a null profile.
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
      }
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, []);

  async function signup({ name, email, password, requestAdmin = false }) {
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
    if (data.session) await refreshAccountProfile();
    return data;
  }

  async function login(email, password) {
    const { data, error } = await supabase.auth.signInWithPassword({
      email: email.trim().toLowerCase(),
      password,
    });

    if (error) throw error;
    await refreshAccountProfile();
    return data;
  }

  async function logout() {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        accountProfile,
        profileErrorStatus,
        profileErrorDetail,
        loading,
        profileLoading,
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
