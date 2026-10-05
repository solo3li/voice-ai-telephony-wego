import { create } from "zustand";
import { apiRequest } from "../constants/api";
import { EmployeeProfile, useAuthStore } from "./useAuthStore";

export interface CallQueueMember {
  id: number;
  type: string;
  name: string;
  extension: string;
  department?: string;
  status?: string;
  order: number;
  is_active: boolean;
}

export interface CallQueueItem {
  id: number;
  name: string;
  code: string;
  strategy: string;
  ring_timeout_seconds: number;
  total_timeout_seconds: number;
  fallback_action: string;
  is_active: boolean;
  members: CallQueueMember[];
}

interface DirectoryState {
  employees: EmployeeProfile[];
  queues: CallQueueItem[];
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchDirectory: () => Promise<void>;
  updateEmployeeLiveStatus: (updatedEmp: EmployeeProfile) => void;
}

export const useDirectoryStore = create<DirectoryState>((set, get) => ({
  employees: [],
  queues: [],
  isLoading: false,
  error: null,

  fetchDirectory: async () => {
    const token = useAuthStore.getState().token;
    if (!token) return;

    set({ isLoading: true, error: null });
    try {
      const data = await apiRequest<{
        status: string;
        employees: EmployeeProfile[];
        queues: CallQueueItem[];
      }>("/api/call-center/employees/", { method: "GET" }, token);

      if (data.status === "success") {
        set({
          employees: data.employees,
          queues: data.queues,
          isLoading: false,
        });
      }
    } catch (err: any) {
      set({
        isLoading: false,
        error: err.message || "Failed to load directory",
      });
    }
  },

  updateEmployeeLiveStatus: (updatedEmp: EmployeeProfile) => {
    set((state) => ({
      employees: state.employees.map((emp) =>
        emp.id === updatedEmp.id ? { ...emp, ...updatedEmp } : emp
      ),
    }));
  },
}));
