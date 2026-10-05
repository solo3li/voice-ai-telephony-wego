import { Platform, AppState, AppStateStatus } from "react-native";
import * as Device from "expo-device";
import { apiRequest } from "../constants/api";
import { useAuthStore } from "../stores/useAuthStore";
import { useCallStore } from "../stores/useCallStore";
import { notificationService } from "./notificationService";

class WatchdogService {
  private timer: ReturnType<typeof setInterval> | null = null;
  private isRunning: boolean = false;
  private appStateSubscription: any = null;
  private lastHeartbeat: number = 0;

  start() {
    if (this.isRunning) return;
    this.isRunning = true;
    console.log("[WatchdogService] Starting 24/7 Keep-Alive Watchdog...");

    // Send immediate heartbeat
    this.sendHeartbeat();

    // Start 30-second interval
    this.timer = setInterval(() => {
      this.sendHeartbeat();
    }, 30000);

    // Monitor AppState transitions
    if (!this.appStateSubscription) {
      this.appStateSubscription = AppState.addEventListener(
        "change",
        (nextState: AppStateStatus) => {
          if (nextState === "active") {
            // Screen unlocked or returned to foreground: ping immediately
            this.sendHeartbeat();
          }
        }
      );
    }
  }

  stop() {
    this.isRunning = false;
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    if (this.appStateSubscription) {
      this.appStateSubscription.remove();
      this.appStateSubscription = null;
    }
    console.log("[WatchdogService] Keep-Alive Watchdog stopped.");
  }

  async sendHeartbeat() {
    const authState = useAuthStore.getState();
    const token = authState.token;
    if (!token || !authState.employee) return;

    try {
      this.lastHeartbeat = Date.now();
      const deviceInfo = {
        platform: Platform.OS,
        brand: Device.brand || "",
        manufacturer: Device.manufacturer || "",
        modelName: Device.modelName || "",
        osVersion: Device.osVersion || "",
      };

      const res = await apiRequest(
        "/api/call-center/employees/heartbeat/",
        {
          method: "POST",
          body: JSON.stringify({ device: deviceInfo }),
        },
        token
      );

      // Check if persistent service notification is active when employee is ready
      if (authState.employee?.status === "ready") {
        notificationService.startPersistentServiceNotification(
          authState.employee.display_name,
          authState.employee.extension
        );
      }

      // Check if server returned an active call that wasn't picked up yet
      if (res && res.active_call) {
        console.log("[WatchdogService] Active call detected during heartbeat:", res.active_call);
        useCallStore.getState().checkActiveIncomingCall();
      }

      // Re-verify centrifuge connection if user is logged in
      const centrifuge = (useCallStore.getState() as any).centrifuge;
      if (centrifuge && centrifuge.state !== "connected" && centrifuge.state !== "connecting") {
        console.log("[WatchdogService] Centrifugo disconnected, reviving connection...");
        try {
          centrifuge.connect();
        } catch (ce) {
          console.warn("[WatchdogService] Centrifugo revive error:", ce);
        }
      }
    } catch (err) {
      console.warn("[WatchdogService] Heartbeat ping failed (retrying next cycle):", err);
    }
  }

  getLastHeartbeatTimestamp(): number {
    return this.lastHeartbeat;
  }
}

export const watchdogService = new WatchdogService();
