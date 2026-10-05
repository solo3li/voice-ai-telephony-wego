import React, { createContext, useContext, useEffect } from "react";
import { Linking, Platform, Alert } from "react-native";
import { ContactItem, CallRecord } from "../constants/mockData";
import { useCallStore, CallState, TabKey, ActiveCallData } from "../stores/useCallStore";

export type { TabKey, CallState, ActiveCallData };

interface CallContextType {
  activeTab: TabKey;
  setActiveTab: (tab: TabKey) => void;
  callState: CallState;
  setCallState: (state: CallState) => void;
  activeCall: ActiveCallData;
  isMuted: boolean;
  isOnHold: boolean;
  dialpadInput: string;
  setDialpadInput: (val: string) => void;
  history: CallRecord[];
  historyFilter: "all" | "missed";
  setHistoryFilter: (filter: "all" | "missed") => void;
  contacts: ContactItem[];
  transferModalVisible: boolean;
  setTransferModalVisible: (visible: boolean) => void;
  playingAudioId: string | null;
  setPlayingAudioId: (id: string | null) => void;

  // Transfer State
  transferId: string | null;
  transferTargetName: string;
  transferDurationSeconds: number;
  cancelTransfer: () => Promise<void>;

  // Actions
  toggleMute: () => void;
  toggleHold: () => void;
  endCall: () => void;
  startCall: (number?: string, name?: string) => void;
  answerCall: () => void;
  declineCall: () => void;
  transferCall: (target: string | ContactItem, name?: string) => void;
  sendWhatsAppOrSms: () => void;
  simulateIncomingCall: () => void;
  resetToDefaultMock: () => void;
}

const CallContext = createContext<CallContextType | undefined>(undefined);

export const CallProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const store = useCallStore();

  const sendWhatsAppOrSms = () => {
    const rawNumber = store.activeCall.phoneNumber.replace(/[^0-9+]/g, "");
    if (!rawNumber) return;
    const url = `https://wa.me/${rawNumber.replace("+", "")}`;
    if (Platform.OS === "web") {
      window.open(url, "_blank");
    } else {
      Linking.openURL(url).catch(() => Alert.alert("Error", "Cannot open WhatsApp"));
    }
  };

  const transferCall = (target: string | ContactItem, name?: string) => {
    if (typeof target === "string") {
      store.transferCall(target, name);
    } else if (target && typeof target === "object") {
      store.transferCall(target.extension, target.name);
    }
  };

  const resetToDefaultMock = () => {
    store.endCall();
  };

  const value: CallContextType = {
    activeTab: store.activeTab,
    setActiveTab: store.setActiveTab,
    callState: store.callState,
    setCallState: (state: CallState) => useCallStore.setState({ callState: state }),
    activeCall: store.activeCall,
    isMuted: store.isMuted,
    isOnHold: store.isOnHold,
    dialpadInput: store.dialpadInput,
    setDialpadInput: store.setDialpadInput,
    history: store.history,
    historyFilter: store.historyFilter,
    setHistoryFilter: store.setHistoryFilter,
    contacts: store.contacts,
    transferModalVisible: store.transferModalVisible,
    setTransferModalVisible: store.setTransferModalVisible,
    playingAudioId: store.playingAudioId,
    setPlayingAudioId: store.setPlayingAudioId,

    transferId: store.transferId,
    transferTargetName: store.transferTargetName,
    transferDurationSeconds: store.transferDurationSeconds,
    cancelTransfer: store.cancelTransfer,

    toggleMute: store.toggleMute,
    toggleHold: store.toggleHold,
    endCall: store.forceEndCall,
    startCall: store.startCall,
    answerCall: store.answerCall,
    declineCall: store.declineCall,
    transferCall,
    sendWhatsAppOrSms,
    simulateIncomingCall: store.simulateIncomingCall,
    resetToDefaultMock,
  };

  return <CallContext.Provider value={value}>{children}</CallContext.Provider>;
};

export const useCall = () => {
  const context = useContext(CallContext);
  if (!context) {
    throw new Error("useCall must be used within a CallProvider");
  }
  return context;
};
