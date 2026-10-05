import { Platform } from "react-native";
import * as Notifications from "expo-notifications";
import * as Device from "expo-device";
import Constants from "expo-constants";
import { apiRequest } from "../constants/api";
import { useAuthStore } from "../stores/useAuthStore";
import { useCallStore } from "../stores/useCallStore";

// Configure how notifications should be handled when app is in foreground
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
    shouldShowBanner: true,
    shouldShowList: true,
  } as any),
});

export interface IncomingCallNotificationData {
  roomName: string;
  callerName: string;
  callerExtension?: string;
  callerDepartment?: string;
  callType?: string;
  queueName?: string;
  transferId?: string;
  transferredBy?: string;
}

class NotificationService {
  private isRegistered = false;
  private responseSubscription: any = null;
  private receivedSubscription: any = null;

  async registerForPushNotifications(): Promise<string | null> {
    if (Platform.OS === "web") {
      console.log("[NotificationService] Push notifications are not supported on web.");
      return null;
    }

    try {
      // 1. Setup Interactive Notification Categories (Answer / Decline buttons)
      await Notifications.setNotificationCategoryAsync("INCOMING_CALL", [
        {
          identifier: "ACTION_ANSWER",
          buttonTitle: "🟢 رد (قبول المكالمة)",
          options: {
            opensAppToForeground: true,
          },
        },
        {
          identifier: "ACTION_DECLINE",
          buttonTitle: "🔴 رفض المكالمة",
          options: {
            isDestructive: true,
            opensAppToForeground: false,
          },
        },
      ]);

      // 2. Android Notification Channel configuration for high priority incoming calls
      if (Platform.OS === "android") {
        await Notifications.setNotificationChannelAsync("call-notifications", {
          name: "مكالمات الموظف الفورية (VoIP)",
          importance: Notifications.AndroidImportance.MAX,
          vibrationPattern: [0, 600, 300, 600, 300, 1000],
          lightColor: "#8b1d36",
          sound: "default",
          enableLights: true,
          enableVibrate: true,
          lockscreenVisibility: Notifications.AndroidNotificationVisibility.PUBLIC,
          bypassDnd: true,
          showBadge: true,
        });

        await Notifications.setNotificationChannelAsync("softphone-service", {
          name: "خدمة الاتصال الدائمة (24/7)",
          importance: Notifications.AndroidImportance.LOW,
          sound: null,
          enableLights: false,
          enableVibrate: false,
          showBadge: false,
          lockscreenVisibility: Notifications.AndroidNotificationVisibility.SECRET,
        });
      }

      // 3. Request user permissions
      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;
      if (existingStatus !== "granted") {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }

      if (finalStatus !== "granted") {
        console.warn("[NotificationService] Push notification permission not granted:", finalStatus);
        return null;
      }

      if (!Device.isDevice) {
        console.log("[NotificationService] Not running on physical device, skipping remote token acquisition.");
        this.setupNotificationListeners();
        return null;
      }

      // 4. Resolve Project ID for Expo Push Service
      const projectId =
        Constants?.expoConfig?.extra?.eas?.projectId ??
        Constants?.easConfig?.projectId;

      const tokenData = await Notifications.getExpoPushTokenAsync(
        projectId ? { projectId } : undefined
      );
      const pushToken = tokenData.data;
      console.log("[NotificationService] Expo Push Token obtained:", pushToken);

      // 5. Send token to Django backend
      await this.sendTokenToBackend(pushToken);
      this.isRegistered = true;

      // 6. Setup event listeners
      this.setupNotificationListeners();

      return pushToken;
    } catch (e) {
      console.warn("[NotificationService] Error registering for push notifications:", e);
      this.setupNotificationListeners();
      return null;
    }
  }

  async sendTokenToBackend(pushToken: string) {
    const authToken = useAuthStore.getState().token;
    if (!authToken || !pushToken) return;

    try {
      await apiRequest(
        "/api/call-center/employees/push-token/",
        {
          method: "POST",
          body: JSON.stringify({ push_token: pushToken }),
        },
        authToken
      );
      console.log("[NotificationService] Push token successfully synchronized with server.");
    } catch (err) {
      console.error("[NotificationService] Failed to send push token to backend:", err);
    }
  }

  async presentIncomingCallNotification(callData: IncomingCallNotificationData) {
    if (Platform.OS === "web") return;
    try {
      let title = "📞 مكالمة صوتية واردة";
      if (callData.queueName) {
        title = `📥 مكالمة طابور: ${callData.queueName}`;
      } else if (callData.callType === "transfer") {
        title = `🔄 مكالمة محولة ${callData.transferredBy ? `من ${callData.transferredBy}` : ""}`;
      } else if (callData.callerName) {
        title = `📞 مكالمة واردة من ${callData.callerName}`;
      }

      const body = `👤 ${callData.callerName || "متصل"} • 🏢 ${callData.callerDepartment || "داخلي"} • تحويلة #${callData.callerExtension || "داخلي"}`;

      await Notifications.scheduleNotificationAsync({
        content: {
          title,
          body,
          subtitle: "⚡ صوت فوري WebRTC HD",
          color: "#8b1d36",
          data: {
            event: "incoming_call",
            room_name: callData.roomName,
            caller_name: callData.callerName,
            caller_extension: callData.callerExtension,
            caller_department: callData.callerDepartment,
            call_type: callData.callType,
            queue_name: callData.queueName,
            transfer_id: callData.transferId,
            transferred_by: callData.transferredBy,
          },
          categoryIdentifier: "INCOMING_CALL",
          sound: "default",
          priority: Notifications.AndroidNotificationPriority.MAX,
          vibrate: [0, 600, 300, 600, 300, 1000],
          sticky: true,
          autoDismiss: false,
        },
        trigger: null, // deliver immediately
      });
    } catch (e) {
      console.warn("[NotificationService] Error scheduling incoming call notification:", e);
    }
  }

  async startPersistentServiceNotification(employeeName: string, extension: string) {
    if (Platform.OS === "web") return;
    try {
      await Notifications.scheduleNotificationAsync({
        identifier: "PERSISTENT_SOFTPHONE_SERVICE",
        content: {
          title: "🟢 بوابة الموظف | الخط متاح (24/7)",
          body: `الموظف: ${employeeName} • تحويلة #${extension} • جاهز للمكالمات`,
          color: "#8b1d36",
          sticky: true,
          autoDismiss: false,
          priority: Notifications.AndroidNotificationPriority.LOW,
          data: { event: "persistent_service" },
        },
        trigger: null,
      });
    } catch (e) {
      console.warn("[NotificationService] Error setting persistent service notification:", e);
    }
  }

  async stopPersistentServiceNotification() {
    if (Platform.OS === "web") return;
    try {
      await Notifications.dismissNotificationAsync("PERSISTENT_SOFTPHONE_SERVICE");
    } catch (e) {}
  }

  async dismissCallNotifications() {
    if (Platform.OS === "web") return;
    try {
      await Notifications.dismissAllNotificationsAsync();
      // Re-schedule persistent service notification if authenticated
      const auth = useAuthStore.getState();
      if (auth.isAuthenticated && auth.employee) {
        this.startPersistentServiceNotification(auth.employee.display_name, auth.employee.extension);
      }
    } catch (e) {
      // Ignore dismiss error
    }
  }

  private setupNotificationListeners() {
    if (this.responseSubscription || this.receivedSubscription) return;

    // Triggered when notification is received while app is open
    this.receivedSubscription = Notifications.addNotificationReceivedListener((notification) => {
      const data = (notification.request.content.data || {}) as Record<string, any>;
      console.log("[NotificationService] Notification received:", data);
    });

    // Triggered when user interacts with notification (clicks Answer, Decline, or taps the notification)
    this.responseSubscription = Notifications.addNotificationResponseReceivedListener((response) => {
      const data = (response.notification.request.content.data || {}) as Record<string, any>;
      const actionIdentifier = response.actionIdentifier;
      console.log("[NotificationService] Notification action triggered:", actionIdentifier, data);

      if (data && data.room_name && data.event === "incoming_call") {
        const incomingCallData = {
          roomName: String(data.room_name),
          callerName: String(data.caller_name || "متصل وارد"),
          callerExtension: String(data.caller_extension || ""),
          callerDepartment: String(data.caller_department || ""),
          callType: (data.call_type || "direct_internal") as any,
          queueName: data.queue_name ? String(data.queue_name) : undefined,
          transferId: data.transfer_id ? String(data.transfer_id) : undefined,
          transferredBy: data.transferred_by ? String(data.transferred_by) : undefined,
        };

        if (actionIdentifier === "ACTION_DECLINE") {
          useCallStore.setState({ incomingCall: incomingCallData });
          useCallStore.getState().declineCall();
          this.dismissCallNotifications();
        } else if (actionIdentifier === "ACTION_ANSWER") {
          useCallStore.setState({
            incomingCall: incomingCallData,
            incomingModalVisible: false,
          });
          useCallStore.getState().answerCall();
          this.dismissCallNotifications();
        } else {
          // Default tap on notification banner -> open full-screen incoming call UI
          useCallStore.setState({
            incomingCall: incomingCallData,
            incomingModalVisible: true,
          });
        }
      }
    });
  }

  cleanup() {
    if (this.receivedSubscription) {
      this.receivedSubscription.remove();
      this.receivedSubscription = null;
    }
    if (this.responseSubscription) {
      this.responseSubscription.remove();
      this.responseSubscription = null;
    }
  }
}

export const notificationService = new NotificationService();
