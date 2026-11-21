import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import type { ReactNode } from "react";
import type { AuthSession } from "./types";
import { ApiError, authApi, errorMessage } from "./lib/api";

interface AuthContextValue {
  session: AuthSession | null;
  loading: boolean;
  restoreError: string;
  restore: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [restoreError, setRestoreError] = useState("");
  const restore = useCallback(async () => {
    setLoading(true);
    setRestoreError("");
    try {
      setSession(await authApi.me());
    } catch (error) {
      setSession(null);
      if (!(error instanceof ApiError && error.status === 401))
        setRestoreError(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void restore();
  }, [restore]);

  return (
    <AuthContext.Provider
      value={{
        session,
        loading,
        restoreError,
        restore,
        login: async (email, password) => {
          setSession(await authApi.login(email, password));
        },
        register: async (name, email, password) => {
          setSession(await authApi.register(name, email, password));
        },
        logout: async () => {
          try {
            if (session) await authApi.logout(session.csrf_token);
          } catch (error) {
            if (!(error instanceof ApiError && error.status === 401))
              throw error;
          }
          setSession(null);
        },
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("AuthProvider is required");
  return auth;
}
