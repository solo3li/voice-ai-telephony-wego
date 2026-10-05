import { create } from "zustand";
import { Platform, PermissionsAndroid } from "react-native";
import { Room, RoomEvent, Track, RemoteTrack, RemoteParticipant } from "livekit-client";
import { Centrifuge } from "centrifuge";
import { apiRequest } from "../constants/api";
import { soundService } from "../services/soundService";
import { notificationService } from "../services/notificationService";
import { useAuthStore } from "./useAuthStore";
import { useDirectoryStore } from "./useDirectoryStore";
import { MOCK_HISTORY, CallRecord, ContactItem, MOCK_CONTACTS } from "../constants/mockData";

export type CallState = "IDLE" | "DIALING" | "RINGING" | "CONNECTED" | "ON_HOLD" | "TRANSFERRING" | "HOLD";
export type TabKey = "dialpad" | "history" | "contacts";

export interface ActiveCallData {
  callerName: string;
  phoneNumber: string;
  extension?: string;
  durationSeconds: number;
  sentiment: string;
  summaryBullets: string[];
  roomName: string;
}

export interface IncomingCallData {
  roomName: string;
  callerName: string;
  callerExtension: string;
  callerDepartment: string;
  callType: "direct_internal" | "queue" | "transfer" | "ring_back";
  queueName?: string;
  transferId?: string;
  transferredBy?: string;
  ringTimeoutSeconds?: number;
}

interface CallStoreState {
  activeTab: TabKey;
  callState: CallState;
  activeCall: ActiveCallData;
  incomingCall: IncomingCallData | null;
  isMuted: boolean;
  isOnHold: boolean;
  dialpadInput: string;
  history: CallRecord[];
  historyFilter: "all" | "missed";
  contacts: ContactItem[];
  transferModalVisible: boolean;
  incomingModalVisible: boolean;
  playingAudioId: string | null;

  // Transfer State
  transferId: string | null;
  transferTargetName: string;
  transferDurationSeconds: number;

  // Real-time connections
  livekitRoom: Room | null;
  centrifuge: Centrifuge | null;

  // Actions
  setActiveTab: (tab: TabKey) => void;
  setDialpadInput: (val: string) => void;
  setHistoryFilter: (filter: "all" | "missed") => void;
  setTransferModalVisible: (visible: boolean) => void;
  setIncomingModalVisible: (visible: boolean) => void;
  setPlayingAudioId: (id: string | null) => void;

  // Call Lifecycle
  initSignaling: () => void;
  disconnectSignaling: () => void;
  checkActiveIncomingCall: () => Promise<void>;
  startCall: (targetNumberOrExt?: string, targetName?: string) => Promise<void>;
  answerCall: () => Promise<void>;
  declineCall: () => void;
  endCall: () => void;
  forceEndCall: () => void;
  toggleMute: () => void;
  toggleHold: () => void;
  transferCall: (targetExtension: string, targetName?: string) => Promise<void>;
  cancelTransfer: () => Promise<void>;
  connectLiveKitRoom: (url: string, token: string, roomName: string, partnerName?: string) => Promise<void>;
  simulateIncomingCall: () => void;
}

let callTimerInterval: any = null;
let isTransferring = false;
let holdAudioInstance: any = null;

const playHoldAudio = () => {
  if (Platform.OS === "web" && typeof window !== "undefined") {
    try {
      if (holdAudioInstance) {
        return; // Audio is already created / playing
      }
      const audio = new Audio("https://assets.mixkit.co/active_storage/sfx/2874/2874-preview.mp3");
      audio.loop = true;
      holdAudioInstance = audio;
      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise.catch((e) => {
          console.log("Hold audio autoplay info:", e?.name || e);
        });
      }
    } catch (e) {
      console.warn("Hold audio creation error:", e);
    }
  }
};

const stopHoldAudio = () => {
  if (holdAudioInstance) {
    const audio = holdAudioInstance;
    holdAudioInstance = null;
    try {
      audio.pause();
      audio.currentTime = 0;
    } catch (e) {}
  }
};

const INITIAL_CALL_DATA: ActiveCallData = {
  callerName: "",
  phoneNumber: "",
  durationSeconds: 0,
  sentiment: "Positive / جيدة",
  summaryBullets: [
    "مكالمة صوتية مشفرة بتقنية WebRTC",
    "جودة صوت نقية وفورية بدون زمن تأخير",
  ],
  roomName: "",
};

async function ensureAudioPermission(): Promise<boolean> {
  if (Platform.OS === "android") {
    try {
      const granted = await PermissionsAndroid.request(
        PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
        {
          title: "إذن استخدام الميكروفون",
          message: "يحتاج تطبيق بوابة الموظف إلى إذن الميكروفون لإجراء واستقبال المكالمات الصوتية.",
          buttonPositive: "موافق",
          buttonNegative: "إلغاء",
        }
      );
      return granted === PermissionsAndroid.RESULTS.GRANTED;
    } catch (err) {
      console.warn("Failed to request Android audio permissions:", err);
      return false;
    }
  }
  return true;
}

export const useCallStore = create<CallStoreState>((set, get) => ({
  activeTab: "dialpad",
  callState: "IDLE",
  activeCall: INITIAL_CALL_DATA,
  incomingCall: null,
  isMuted: false,
  isOnHold: false,
  dialpadInput: "",
  history: [],
  historyFilter: "all",
  contacts: [],
  transferModalVisible: false,
  incomingModalVisible: false,
  playingAudioId: null,

  transferId: null,
  transferTargetName: "",
  transferDurationSeconds: 0,

  livekitRoom: null,
  centrifuge: null,

  setActiveTab: (tab: TabKey) => set({ activeTab: tab }),
  setDialpadInput: (val: string) => set({ dialpadInput: val }),
  setHistoryFilter: (filter: "all" | "missed") => set({ historyFilter: filter }),
  setTransferModalVisible: (visible: boolean) => set({ transferModalVisible: visible }),
  setIncomingModalVisible: (visible: boolean) => set({ incomingModalVisible: visible }),
  setPlayingAudioId: (id: string | null) => set({ playingAudioId: id }),

  initSignaling: () => {
    const auth = useAuthStore.getState();
    const config = auth.centrifugoConfig;
    if (!config || !auth.employee) return;

    // Disconnect previous instance if any
    const existing = get().centrifuge;
    if (existing) {
      existing.disconnect();
    }

    try {
      const centrifuge = new Centrifuge(config.ws_url, {
        token: config.token,
        timeout: 5000,
        minReconnectDelay: 500,
        maxReconnectDelay: 5000,
        maxServerPingDelay: 10000,
      });

      // 1. Personal Employee Channel for direct incoming calls & transfers
      const empSub = centrifuge.newSubscription(config.channel);
      empSub.on("publication", (ctx) => {
        const payload = ctx.data;
        console.log("[Centrifugo Event]", payload.event, payload);

        if (payload.event === "incoming_call") {
          soundService.playIncomingRingtone();
          const callInfo: IncomingCallData = {
            roomName: payload.room_name,
            callerName: payload.caller_name || "متصل غير معروف",
            callerExtension: payload.caller_extension || "",
            callerDepartment: payload.caller_department || "",
            callType: payload.call_type || "direct_internal",
            queueName: payload.queue_name,
            transferId: payload.transfer_id,
            transferredBy: payload.transferred_by,
            ringTimeoutSeconds: payload.ring_timeout_seconds,
          };
          set({
            incomingCall: callInfo,
            incomingModalVisible: true,
          });
          notificationService.presentIncomingCallNotification({
            roomName: callInfo.roomName,
            callerName: callInfo.callerName,
            callerExtension: callInfo.callerExtension,
            callerDepartment: callInfo.callerDepartment,
            callType: callInfo.callType,
            queueName: callInfo.queueName,
            transferId: callInfo.transferId,
            transferredBy: callInfo.transferredBy,
          });
        } else if (payload.event === "transfer_hold") {
          // Caller is put on local hold
          isTransferring = true;
          const currentRoom = get().livekitRoom;
          if (currentRoom) {
            try { currentRoom.disconnect(); } catch (e) {}
          }
          if (callTimerInterval) {
            clearInterval(callTimerInterval);
            callTimerInterval = null;
          }
          playHoldAudio();
          set((state) => ({
            callState: "HOLD",
            transferId: payload.transfer_id,
            livekitRoom: null,
            activeCall: {
              ...state.activeCall,
              callerName: payload.target_name ? `تحويل إلى: ${payload.target_name}` : "جاري التحويل...",
              summaryBullets: [
                "المكالمة قيد التحويل إلى زميل متاح",
                "نغمة الانتظار تعمل حتى قبول الطرف الآخر",
              ],
            },
          }));
          callTimerInterval = setInterval(() => {
            set((state) => ({
              activeCall: {
                ...state.activeCall,
                durationSeconds: state.activeCall.durationSeconds + 1,
              },
            }));
          }, 1000);
        } else if (payload.event === "transfer_room_ready") {
          // New LiveKit room is ready
          isTransferring = false;
          stopHoldAudio();
          set({
            transferId: null,
          });
          get().connectLiveKitRoom(
            payload.livekit_url,
            payload.livekit_token,
            payload.room_name,
            payload.partner_name || "الطرف الآخر"
          );
        } else if (payload.event === "transfer_success") {
          // Transferrer already detached; log confirmation
          console.log("Transfer succeeded:", payload);
        } else if (payload.event === "transfer_cancelled") {
          // If employee is IDLE, ignore cancellation/reconnection
          if (get().callState === "IDLE") {
            console.log("Ignoring transfer_cancelled because employee is IDLE");
            return;
          }
          isTransferring = false;
          stopHoldAudio();
          alert("تم إلغاء التحويل واستعادة المكالمة");
          get().connectLiveKitRoom(
            payload.livekit_url,
            payload.livekit_token,
            payload.room_name,
            payload.partner_name || "الزميل"
          );
        } else if (payload.event === "transfer_failed") {
          // If employee is already IDLE (detached) or in an active call, ignore!
          if (get().callState === "IDLE" || (get().callState === "CONNECTED" && !isTransferring && !get().transferId)) {
            console.log("Suppressing stray transfer_failed because employee is not on hold/transferring");
            return;
          }
          isTransferring = false;
          stopHoldAudio();
          alert(`فشل التحويل: ${payload.message || "لم يرد أحد على المكالمة"}`);
          get().forceEndCall();
        } else if (payload.event === "call_ended") {
          if (isTransferring || get().callState === "HOLD" || get().callState === "TRANSFERRING") {
            console.log("Suppressing call_ended because call is currently in transfer/hold state:", payload);
            return;
          }
          stopHoldAudio();
          get().forceEndCall();
        }
      });
      empSub.subscribe();

      // 2. Presence Channel for live status updates of coworkers
      const presenceSub = centrifuge.newSubscription("employees:presence");
      presenceSub.on("publication", (ctx) => {
        const payload = ctx.data;
        if (payload.event === "status_change" && payload.employee) {
          useDirectoryStore.getState().updateEmployeeLiveStatus(payload.employee);
        }
      });
      presenceSub.subscribe();

      // 3. Queue Broadcast Channel
      const queueSub = centrifuge.newSubscription("queues:broadcast");
      queueSub.on("publication", (ctx) => {
        const payload = ctx.data;
        if (payload.event === "call_accepted") {
          if (get().incomingCall?.roomName === payload.room_name) {
            const currentEmpId = useAuthStore.getState().employee?.id;
            if (payload.accepted_by?.id !== currentEmpId) {
              set({ incomingModalVisible: false, incomingCall: null });
            }
          }
        }
      });
      queueSub.subscribe();

      centrifuge.on("connected", () => {
        console.log("[Centrifugo] Connected. Checking active incoming call...");
        get().checkActiveIncomingCall();
      });

      centrifuge.connect();
      set({ centrifuge });
    } catch (e) {
      console.error("Centrifugo initialization failed:", e);
    }
  },

  disconnectSignaling: () => {
    stopHoldAudio();
    const { centrifuge, livekitRoom } = get();
    if (centrifuge) centrifuge.disconnect();
    if (livekitRoom) livekitRoom.disconnect();
    set({ centrifuge: null, livekitRoom: null });
  },

  checkActiveIncomingCall: async () => {
    const token = useAuthStore.getState().token;
    if (!token) return;
    const currentState = get().callState;
    if (currentState !== "IDLE" && currentState !== "RINGING") return;

    try {
      const res = await apiRequest("/api/call-center/employees/active-incoming/", { method: "GET" }, token);
      if (res && res.status === "ringing" && res.incoming_call) {
        const call = res.incoming_call;
        if (get().incomingCall?.roomName === call.room_name) return;

        console.log("[useCallStore] Recovered active ringing call from server:", call);
        soundService.playIncomingRingtone();
        const callInfo: IncomingCallData = {
          roomName: call.room_name,
          callerName: call.caller_name || "متصل غير معروف",
          callerExtension: call.caller_extension || "",
          callerDepartment: call.caller_department || "",
          callType: call.call_type || "direct_internal",
          queueName: call.queue_name,
          transferId: call.transfer_id,
          transferredBy: call.transferred_by,
          ringTimeoutSeconds: call.ring_timeout_seconds,
        };
        set({
          incomingCall: callInfo,
          incomingModalVisible: true,
        });
        notificationService.presentIncomingCallNotification({
          roomName: callInfo.roomName,
          callerName: callInfo.callerName,
          callerExtension: callInfo.callerExtension,
          callerDepartment: callInfo.callerDepartment,
          callType: callInfo.callType,
          queueName: callInfo.queueName,
          transferId: callInfo.transferId,
          transferredBy: callInfo.transferredBy,
        });
      } else if (res && res.status === "idle") {
        if (get().incomingCall && get().callState === "IDLE") {
          soundService.stopAll();
          notificationService.dismissCallNotifications();
          set({ incomingCall: null, incomingModalVisible: false });
        }
      }
    } catch (err) {
      console.warn("[useCallStore] Error checking active incoming call:", err);
    }
  },

  connectLiveKitRoom: async (livekitUrl: string, livekitToken: string, roomName: string, partnerName?: string) => {
    soundService.stopAll();
    const existing = get().livekitRoom;
    if (existing) {
      try { existing.disconnect(); } catch (e) {}
    }

    if (callTimerInterval) {
      clearInterval(callTimerInterval);
      callTimerInterval = null;
    }

    set((state) => ({
      callState: "CONNECTED",
      incomingModalVisible: false,
      incomingCall: null,
      transferId: null,
      activeCall: {
        ...state.activeCall,
        roomName,
        callerName: partnerName || state.activeCall.callerName || "مكالمة نشطة",
        durationSeconds: 0,
      },
    }));

    callTimerInterval = setInterval(() => {
      set((state) => ({
        activeCall: {
          ...state.activeCall,
          durationSeconds: state.activeCall.durationSeconds + 1,
        },
      }));
    }, 1000);

    await ensureAudioPermission();

    const room = new Room({
      adaptiveStream: true,
      dynacast: true,
    });

    room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
      if (track.kind === Track.Kind.Audio) {
        if (Platform.OS === "web") {
          const el = track.attach();
          el.play().catch((e) => console.log("Audio play error:", e));
        } else {
          try { track.attach(); } catch (e) { console.log("Native audio attach:", e); }
        }
      }
    });

    room.on(RoomEvent.ParticipantDisconnected, (participant: RemoteParticipant) => {
      if (isTransferring || get().callState === "HOLD" || get().callState === "TRANSFERRING") {
        console.log("Ignoring participant disconnect during transfer/hold");
        return;
      }

      // Ignore bots, ai-agent, queue workers, and transfer helpers
      const isHumanPeer =
        participant.identity.startsWith("employee_") ||
        participant.identity.startsWith("customer_") ||
        participant.identity.startsWith("user_");

      if (!isHumanPeer) {
        console.log("Ignoring non-human participant disconnect:", participant.identity);
        return;
      }

      console.log("Remote human participant disconnected:", participant.identity);
      const remainingHumans = Array.from(room.remoteParticipants.values()).filter(
        (p) =>
          p.identity !== participant.identity &&
          (p.identity.startsWith("employee_") ||
           p.identity.startsWith("customer_") ||
           p.identity.startsWith("user_"))
      );
      if (remainingHumans.length === 0) {
        get().endCall();
      }
    });

    room.on(RoomEvent.Disconnected, () => {
      if (isTransferring || get().callState === "HOLD" || get().callState === "TRANSFERRING") {
        console.log("Ignoring room disconnect during transfer/hold");
        return;
      }
      get().endCall();
    });

    await room.connect(livekitUrl, livekitToken);

    // Attach any tracks that arrived early on web
    if (Platform.OS === "web") {
      room.remoteParticipants.forEach((p) => {
        p.trackPublications.forEach((pub) => {
          if (pub.track && pub.track.kind === Track.Kind.Audio) {
            const el = pub.track.attach();
            el.play().catch((e) => console.log("Audio attach error:", e));
          }
        });
      });
    }

    try {
      await room.localParticipant.setMicrophoneEnabled(true);
    } catch (micErr) {
      console.warn("Failed to enable mic:", micErr);
    }

    set({ livekitRoom: room });
  },

  startCall: async (targetNumberOrExt?: string, targetName?: string) => {
    const target = targetNumberOrExt || get().dialpadInput.trim();
    if (!target) {
      alert("الرجاء إدخال رقم هاتف أو تحويلة للاتصال");
      return;
    }

    const token = useAuthStore.getState().token;
    if (!token) {
      alert("يرجى تسجيل الدخول للاتصال");
      return;
    }

    set({
      callState: "DIALING",
      activeCall: {
        callerName: targetName || `تحويلة: ${target}`,
        phoneNumber: target,
        extension: target,
        durationSeconds: 0,
        sentiment: "Positive / جيدة",
        summaryBullets: [
          "جاري الاتصال والربط عبر WebRTC...",
          `الطرف الآخر: ${target}`,
        ],
        roomName: "",
      },
    });

    try {
      const data = await apiRequest<{
        status: string;
        room_name: string;
        target_name: string;
        livekit_url: string;
        livekit_token: string;
        call_type: string;
      }>("/api/call-center/calls/dial/", {
        method: "POST",
        body: JSON.stringify({ target }),
      }, token);

      if (data.status === "success") {
        soundService.playOutgoingRingback();
        set((state) => ({
          callState: "RINGING",
          activeCall: {
            ...state.activeCall,
            callerName: data.target_name,
            roomName: data.room_name,
          },
        }));

        await ensureAudioPermission();

        const isAICall = data.call_type === "ai_test" || data.call_type === "ai_call";

        const room = new Room({
          adaptiveStream: true,
          dynacast: true,
        });

        room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
          soundService.stopAll();
          if (get().callState === "RINGING" || get().callState === "DIALING") {
            set({ callState: "CONNECTED" });
          }
          if (track.kind === Track.Kind.Audio) {
            if (Platform.OS === "web") {
              const audioElement = track.attach();
              audioElement.play().catch((err) => console.log("Audio play error:", err));
            } else {
              // Android/iOS: attach returns an element-like obj but audio routes via native LiveKit SDK
              try {
                track.attach();
              } catch (e) {
                console.log("Native audio attach:", e);
              }
            }
          }
          // Start timer when first audio track arrives (covers AI calls where ParticipantConnected may already have fired)
          if (!callTimerInterval) {
            callTimerInterval = setInterval(() => {
              set((state) => ({
                activeCall: {
                  ...state.activeCall,
                  durationSeconds: state.activeCall.durationSeconds + 1,
                },
              }));
            }, 1000);
          }
        });

        room.on(RoomEvent.ParticipantConnected, () => {
          soundService.stopAll();
          set({ callState: "CONNECTED" });
          if (!callTimerInterval) {
            callTimerInterval = setInterval(() => {
              set((state) => ({
                activeCall: {
                  ...state.activeCall,
                  durationSeconds: state.activeCall.durationSeconds + 1,
                },
              }));
            }, 1000);
          }
        });

        room.on(RoomEvent.ParticipantDisconnected, (participant: RemoteParticipant) => {
          if (isTransferring || get().callState === "HOLD" || get().callState === "TRANSFERRING") {
            console.log("Ignoring participant disconnect during transfer/hold");
            return;
          }

          // AI agent identity — treat as call-ender for AI calls
          const isAIAgent = participant.identity === "ai-agent" || participant.identity === "pipecat-agent";
          if (isAIAgent) {
            console.log("AI agent disconnected — ending call");
            soundService.stopAll();
            // Small delay so any final audio finishes playing
            setTimeout(() => {
              get().endCall();
            }, 800);
            return;
          }

          const isHumanPeer =
            participant.identity.startsWith("employee_") ||
            participant.identity.startsWith("customer_") ||
            participant.identity.startsWith("user_");

          if (!isHumanPeer) {
            console.log("Ignoring non-human participant disconnect:", participant.identity);
            return;
          }

          console.log("Remote human participant disconnected:", participant.identity);
          const remainingHumans = Array.from(room.remoteParticipants.values()).filter(
            (p) =>
              p.identity !== participant.identity &&
              (p.identity.startsWith("employee_") ||
               p.identity.startsWith("customer_") ||
               p.identity.startsWith("user_"))
          );
          if (remainingHumans.length === 0) {
            get().endCall();
          }
        });

        room.on(RoomEvent.Disconnected, () => {
          soundService.stopAll();
          if (isTransferring || get().callState === "HOLD" || get().callState === "TRANSFERRING") {
            console.log("Ignoring room disconnect during transfer/hold");
            return;
          }
          get().endCall();
        });

        await room.connect(data.livekit_url, data.livekit_token);

        // Attach any already-published audio tracks (AI may have joined before employee)
        const attachExistingAudioTracks = () => {
          room.remoteParticipants.forEach((p) => {
            p.trackPublications.forEach((pub) => {
              if (pub.isSubscribed && pub.track && pub.track.kind === Track.Kind.Audio) {
                if (Platform.OS === "web") {
                  try {
                    const el = pub.track.attach();
                    el.play().catch((e) => console.log("Audio attach error:", e));
                  } catch (e) { console.log("attach err:", e); }
                } else {
                  try { pub.track.attach(); } catch (e) {}
                }
              }
            });
          });
        };
        attachExistingAudioTracks();
        // Also try again after a short delay in case tracks arrive slightly after connect
        setTimeout(attachExistingAudioTracks, 1500);

        try {
          await room.localParticipant.setMicrophoneEnabled(true);
        } catch (micErr) {
          console.warn("Failed to enable mic:", micErr);
        }

        set({ livekitRoom: room });
      }
    } catch (err: any) {
      alert(`فشل الاتصال: ${err.message}`);
      set({ callState: "IDLE", activeCall: INITIAL_CALL_DATA });
    }
  },

  answerCall: async () => {
    soundService.stopAll();
    notificationService.dismissCallNotifications();
    const { incomingCall } = get();
    const token = useAuthStore.getState().token;
    if (!incomingCall || !token) return;

    // Check if this is an incoming transferred call
    if (incomingCall.callType === "transfer" && incomingCall.transferId) {
      try {
        await apiRequest("/api/call-center/calls/transfer/action/", {
          method: "POST",
          body: JSON.stringify({
            transfer_id: incomingCall.transferId,
            action: "answer",
          }),
        }, token);
        set({ incomingModalVisible: false });
        // The transfer_room_ready Centrifugo event will arrive and connect to LiveKit!
        return;
      } catch (err: any) {
        alert(`فشل الرد على التحويل: ${err.message}`);
        return;
      }
    }

    set({
      callState: "CONNECTED",
      incomingModalVisible: false,
      activeCall: {
        callerName: incomingCall.callerName,
        phoneNumber: incomingCall.callerExtension,
        extension: incomingCall.callerExtension,
        durationSeconds: 0,
        sentiment: "Positive / جيدة",
        summaryBullets: [
          "مكالمة واردة عبر شبكة الكول سنتر WebRTC",
          `المتصل: ${incomingCall.callerName} (تحويلة: ${incomingCall.callerExtension})`,
        ],
        roomName: incomingCall.roomName,
      },
    });

    if (callTimerInterval) clearInterval(callTimerInterval);
    callTimerInterval = setInterval(() => {
      set((state) => ({
        activeCall: {
          ...state.activeCall,
          durationSeconds: state.activeCall.durationSeconds + 1,
        },
      }));
    }, 1000);

    try {
      const data = await apiRequest<{
        status: string;
        room_name: string;
        livekit_url: string;
        livekit_token: string;
      }>("/api/call-center/calls/token/", {
        method: "POST",
        body: JSON.stringify({ room_name: incomingCall.roomName }),
      }, token);

      if (data.status === "success") {
        await ensureAudioPermission();

        const room = new Room({
          adaptiveStream: true,
          dynacast: true,
        });

        room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
          if (track.kind === Track.Kind.Audio) {
            if (Platform.OS === "web") {
              const el = track.attach();
              el.play().catch((e) => console.log("Audio play error:", e));
            }
          }
        });

        room.on(RoomEvent.ParticipantDisconnected, (participant: RemoteParticipant) => {
          if (isTransferring || get().callState === "HOLD" || get().callState === "TRANSFERRING") {
            console.log("Ignoring participant disconnect during transfer/hold");
            return;
          }

          // Ignore bots, ai-agent, queue workers, and transfer helpers
          const isHumanPeer =
            participant.identity.startsWith("employee_") ||
            participant.identity.startsWith("customer_") ||
            participant.identity.startsWith("user_");

          if (!isHumanPeer) {
            console.log("Ignoring non-human participant disconnect:", participant.identity);
            return;
          }

          console.log("Remote human participant disconnected:", participant.identity);
          const remainingHumans = Array.from(room.remoteParticipants.values()).filter(
            (p) =>
              p.identity !== participant.identity &&
              (p.identity.startsWith("employee_") ||
               p.identity.startsWith("customer_") ||
               p.identity.startsWith("user_"))
          );
          if (remainingHumans.length === 0) {
            get().endCall();
          }
        });

        room.on(RoomEvent.Disconnected, () => {
          if (isTransferring || get().callState === "HOLD" || get().callState === "TRANSFERRING") {
            console.log("Ignoring room disconnect during transfer/hold");
            return;
          }
          get().endCall();
        });

        await room.connect(data.livekit_url, data.livekit_token);

        if (Platform.OS === "web") {
          room.remoteParticipants.forEach((p) => {
            p.trackPublications.forEach((pub) => {
              if (pub.track && pub.track.kind === Track.Kind.Audio) {
                const el = pub.track.attach();
                el.play().catch((e) => console.log("Audio attach error:", e));
              }
            });
          });
        }

        try {
          await room.localParticipant.setMicrophoneEnabled(true);
        } catch (micErr) {
          console.warn("Failed to enable mic:", micErr);
        }

        set({ livekitRoom: room, incomingCall: null });
      }
    } catch (err) {
      console.error("Failed to join incoming call room:", err);
    }
  },

  declineCall: () => {
    soundService.stopAll();
    notificationService.dismissCallNotifications();
    const { incomingCall } = get();
    const token = useAuthStore.getState().token;

    if (incomingCall?.callType === "transfer" && incomingCall.transferId && token) {
      apiRequest("/api/call-center/calls/transfer/action/", {
        method: "POST",
        body: JSON.stringify({
          transfer_id: incomingCall.transferId,
          action: "reject",
        }),
      }, token).catch((e) => console.log("Decline transfer error:", e));
    } else if (incomingCall?.roomName && token) {
      apiRequest("/api/call-center/calls/hangup/", {
        method: "POST",
        body: JSON.stringify({ room_name: incomingCall.roomName }),
      }, token).catch((err) => console.log("Decline hangup API error:", err));
    }

    set({ incomingModalVisible: false, incomingCall: null });
  },

  endCall: () => {
    if (isTransferring || get().callState === "HOLD" || get().callState === "TRANSFERRING") {
      console.log("endCall suppressed because call is currently in transfer/hold state");
      return;
    }
    get().forceEndCall();
  },

  forceEndCall: () => {
    soundService.stopAll();
    notificationService.dismissCallNotifications();
    isTransferring = false;
    stopHoldAudio();
    if (callTimerInterval) {
      clearInterval(callTimerInterval);
      callTimerInterval = null;
    }

    const { livekitRoom, activeCall, incomingCall, transferId } = get();
    const roomNameToHangup = activeCall.roomName || incomingCall?.roomName;

    if (livekitRoom) {
      try {
        livekitRoom.disconnect();
      } catch (e) {}
    }

    const token = useAuthStore.getState().token;
    if (token) {
      if (transferId) {
        apiRequest("/api/call-center/calls/transfer/cancel/", {
          method: "POST",
          body: JSON.stringify({ transfer_id: transferId }),
        }, token).catch((err) => console.log("Cancel transfer error on hangup:", err));
      }
      if (roomNameToHangup) {
        apiRequest("/api/call-center/calls/hangup/", {
          method: "POST",
          body: JSON.stringify({ room_name: roomNameToHangup }),
        }, token).catch((err) => console.log("Hangup API error:", err));
      }
    }

    set({
      callState: "IDLE",
      isMuted: false,
      isOnHold: false,
      livekitRoom: null,
      activeCall: INITIAL_CALL_DATA,
      incomingModalVisible: false,
      incomingCall: null,
      transferId: null,
      transferTargetName: "",
      transferDurationSeconds: 0,
    });
  },

  toggleMute: () => {
    const { isMuted, livekitRoom } = get();
    const next = !isMuted;
    set({ isMuted: next });

    if (livekitRoom?.localParticipant) {
      livekitRoom.localParticipant.setMicrophoneEnabled(!next);
    }
  },

  toggleHold: () => {
    const { isOnHold, callState } = get();
    const next = !isOnHold;
    set({
      isOnHold: next,
      callState: next ? "ON_HOLD" : "CONNECTED",
    });
  },

  transferCall: async (targetExtension: string, targetName?: string) => {
    const token = useAuthStore.getState().token;
    const { activeCall, livekitRoom } = get();
    if (!token || !activeCall.roomName) return;

    // Immediately stop audio & disconnect transferring employee
    if (livekitRoom) {
      try { livekitRoom.disconnect(); } catch (e) {}
    }
    if (callTimerInterval) {
      clearInterval(callTimerInterval);
      callTimerInterval = null;
    }
    stopHoldAudio();

    // Reset call state immediately to IDLE so employee is freed and out of the loop
    isTransferring = false;
    set({
      callState: "IDLE",
      isMuted: false,
      isOnHold: false,
      livekitRoom: null,
      activeCall: INITIAL_CALL_DATA,
      incomingModalVisible: false,
      incomingCall: null,
      transferModalVisible: false,
      transferId: null,
      transferTargetName: "",
      transferDurationSeconds: 0,
    });

    // Optimistically update local employee status to ready in useAuthStore
    const currentEmp = useAuthStore.getState().employee;
    if (currentEmp) {
      useAuthStore.setState({
        employee: {
          ...currentEmp,
          status: "ready",
          status_display: "متاح (Ready)",
        },
      });
    }

    try {
      const res = await apiRequest<{
        status: string;
        message: string;
        transfer_id: string;
        target: string;
        target_name: string;
      }>("/api/call-center/calls/transfer/", {
        method: "POST",
        body: JSON.stringify({
          room_name: activeCall.roomName,
          target: targetExtension,
        }),
      }, token);

      alert(`✅ تم تحويل المكالمة بنجاح إلى: ${res.target_name || targetName || targetExtension}\nأنت الآن متاح لاستقبال مكالمات جديدة.`);
    } catch (err: any) {
      alert(`فشل التحويل: ${err.message}`);
    }
  },

  cancelTransfer: async () => {
    // Blind transfer is immediate; cancel is not applicable
  },

  simulateIncomingCall: () => {
    // Demo mock function disabled
  },
}));
