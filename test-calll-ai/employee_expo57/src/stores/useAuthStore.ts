import { create } from "zustand";
import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";
import { apiRequest } from "../constants/api";

export interface EmployeeProfile {
  id: number;
  user_id: number;
  username: string;
  extension: string;
  display_name: string;
  department: string;
  status: "ready" | "break" | "busy" | "offline";
  status_display: string;
  avatar_url: string;
  is_active: boolean;
  is_owner?: boolean;
}

export interface CentrifugoConfig {
  ws_url: string;
  token: string;
  channel: string;
}

interface AuthState {
  token: string | null;
  employee: EmployeeProfile | null;
  centrifugoConfig: CentrifugoConfig | null;
  isAuthenticated: boolean;
  isRestoring: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (identifier: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  updateStatus: (status: "ready" | "break" | "busy") => Promise<void>;
  restoreSession: () => Promise<void>;
  clearError: () => void;
}

const STORAGE_KEY_TOKEN = "employee_auth_token";
const STORAGE_KEY_EMP = "employee_profile";
const STORAGE_KEY_CENT = "centrifugo_config";

async function getStorageItemAsync(key: string): Promise<string | null> {
  try {
    if (Platform.OS === "web") {
      if (typeof window !== "undefined" && window.localStorage) {
        return window.localStorage.getItem(key);
      }
      return null;
    }
    return await SecureStore.getItemAsync(key);
  } catch (e) {
    console.warn(`[useAuthStore] Error reading key "${key}" from SecureStore:`, e);
    return null;
  }
}

async function setStorageItemAsync(key: string, value: string): Promise<void> {
  try {
    if (Platform.OS === "web") {
      if (typeof window !== "undefined" && window.localStorage) {
        window.localStorage.setItem(key, value);
      }
      return;
    }
    await SecureStore.setItemAsync(key, value);
  } catch (e) {
    console.warn(`[useAuthStore] Error saving key "${key}" to SecureStore:`, e);
  }
}

async function removeStorageItemAsync(key: string): Promise<void> {
  try {
    if (Platform.OS === "web") {
      if (typeof window !== "undefined" && window.localStorage) {
        window.localStorage.removeItem(key);
      }
      return;
    }
    await SecureStore.deleteItemAsync(key);
  } catch (e) {
    console.warn(`[useAuthStore] Error removing key "${key}" from SecureStore:`, e);
  }
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  employee: null,
  centrifugoConfig: null,
  isAuthenticated: false,
  isRestoring: true,
  isLoading: false,
  error: null,

  clearError: () => set({ error: null }),

  login: async (identifier: string, password: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    try {
      const data = await apiRequest<{
        status: string;
        token: string;
        employee: EmployeeProfile;
        centrifugo: CentrifugoConfig;
        message?: string;
      }>("/api/call-center/auth/login/", {
        method: "POST",
        body: JSON.stringify({ identifier, password }),
      });

      if (data.status === "success" && data.token) {
        await setStorageItemAsync(STORAGE_KEY_TOKEN, data.token);
        await setStorageItemAsync(STORAGE_KEY_EMP, JSON.stringify(data.employee));
        await setStorageItemAsync(STORAGE_KEY_CENT, JSON.stringify(data.centrifugo));

        set({
          token: data.token,
          employee: data.employee,
          centrifugoConfig: data.centrifugo,
          isAuthenticated: true,
          isRestoring: false,
          isLoading: false,
          error: null,
        });

        // Trigger push notification registration immediately upon successful login
        try {
          const { notificationService } = require("../services/notificationService");
          notificationService.registerForPushNotifications();
        } catch (e) {
          console.warn("[useAuthStore] Push notification registration note:", e);
        }

        return true;
      } else {
        set({
          isLoading: false,
          error: data.message || "فشل تسجيل الدخول",
        });
        return false;
      }
    } catch (err: any) {
      set({
        isLoading: false,
        error: err.message || "حدث خطأ في الاتصال بالخادم",
      });
      return false;
    }
  },

  logout: async () => {
    await removeStorageItemAsync(STORAGE_KEY_TOKEN);
    await removeStorageItemAsync(STORAGE_KEY_EMP);
    await removeStorageItemAsync(STORAGE_KEY_CENT);

    set({
      token: null,
      employee: null,
      centrifugoConfig: null,
      isAuthenticated: false,
      isRestoring: false,
      error: null,
    });
  },

  updateStatus: async (status: "ready" | "break" | "busy") => {
    const { token, employee } = get();
    if (!token || !employee) return;

    // Optimistic UI update
    set({
      employee: {
        ...employee,
        status,
        status_display: status === "ready" ? "متاح (Ready)" : status === "break" ? "استراحة (Break)" : "مشغول (Busy)",
      },
    });

    try {
      const data = await apiRequest<{ status: string; employee: EmployeeProfile }>(
        "/api/call-center/employees/status/",
        {
          method: "POST",
          body: JSON.stringify({ status }),
        },
        token
      );

      if (data.status === "success") {
        await setStorageItemAsync(STORAGE_KEY_EMP, JSON.stringify(data.employee));
        set({ employee: data.employee });
      }
    } catch (err) {
      console.error("Failed to update employee status:", err);
    }
  },

  restoreSession: async () => {
    set({ isRestoring: true, isLoading: true });
    try {
      const token = await getStorageItemAsync(STORAGE_KEY_TOKEN);
      if (!token) {
        set({ isAuthenticated: false, isRestoring: false, isLoading: false });
        return;
      }

      const rawEmp = await getStorageItemAsync(STORAGE_KEY_EMP);
      const rawCent = await getStorageItemAsync(STORAGE_KEY_CENT);
      let cachedEmp: EmployeeProfile | null = null;
      let cachedCent: CentrifugoConfig | null = null;
      try { if (rawEmp) cachedEmp = JSON.parse(rawEmp); } catch {}
      try { if (rawCent) cachedCent = JSON.parse(rawCent); } catch {}

      // Fast optimistic hydration from encrypted local store
      set({
        token,
        employee: cachedEmp,
        centrifugoConfig: cachedCent,
        isAuthenticated: true,
        isRestoring: false,
        isLoading: false,
      });

      // Background verification with backend
      try {
        const data = await apiRequest<{
          status: string;
          employee: EmployeeProfile;
          centrifugo: CentrifugoConfig;
        }>("/api/call-center/auth/me/", { method: "GET" }, token);

        if (data.status === "success") {
          await setStorageItemAsync(STORAGE_KEY_EMP, JSON.stringify(data.employee));
          await setStorageItemAsync(STORAGE_KEY_CENT, JSON.stringify(data.centrifugo));
          set({
            token,
            employee: data.employee,
            centrifugoConfig: data.centrifugo,
            isAuthenticated: true,
            isRestoring: false,
            isLoading: false,
          });
        } else {
          await get().logout();
        }
      } catch (err: any) {
        // If 401 Unauthorized, token has expired on server
        if (err?.status === 401 || err?.message?.includes("401") || err?.message?.includes("Unauthorized")) {
          await get().logout();
        } else {
          // If offline / network error, retain cached authenticated session
          set({ isRestoring: false, isLoading: false });
        }
      }
    } catch (e) {
      console.warn("[useAuthStore] restoreSession unexpected error:", e);
      set({ isRestoring: false, isLoading: false });
    }
  },
}));
