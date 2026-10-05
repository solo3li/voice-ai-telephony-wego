import { Platform } from "react-native";

export const API_BASE_URL = "https://app.169.58.32.179.nip.io";
export const LIVEKIT_DEFAULT_URL = "wss://livekit.169.58.32.179.nip.io";
export const CENTRIFUGO_DEFAULT_WS = "wss://centrifugo.169.58.32.179.nip.io/connection/websocket";

export async function apiRequest<T = any>(
  endpoint: string,
  options: RequestInit = {},
  token?: string | null
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.message || `Request failed with status ${response.status}`);
  }

  return data as T;
}
