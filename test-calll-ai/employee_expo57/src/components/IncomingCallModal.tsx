import * as React from "react";
import {
  View,
  Text,
  StyleSheet,
  Modal,
  TouchableOpacity,
  BackHandler,
  StatusBar,
  SafeAreaView,
  Platform,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Colors } from "../constants/theme";
import { useCallStore } from "../stores/useCallStore";

export const IncomingCallModal: React.FC = () => {
  const incomingModalVisible = useCallStore((s) => s.incomingModalVisible);
  const incomingCall = useCallStore((s) => s.incomingCall);
  const answerCall = useCallStore((s) => s.answerCall);
  const declineCall = useCallStore((s) => s.declineCall);

  // Intercept Android hardware back button while incoming call modal is visible
  React.useEffect(() => {
    if (!incomingModalVisible) return;
    const backHandler = BackHandler.addEventListener("hardwareBackPress", () => {
      declineCall();
      return true;
    });
    return () => backHandler.remove();
  }, [incomingModalVisible, declineCall]);

  if (!incomingModalVisible || !incomingCall) return null;

  const isQueue = incomingCall.callType === "queue";
  const isTransfer = incomingCall.callType === "transfer";
  const isRingBack = incomingCall.callType === "ring_back";

  return (
    <Modal
      visible={incomingModalVisible}
      transparent={false}
      animationType="fade"
      statusBarTranslucent={true}
    >
      <StatusBar barStyle="light-content" backgroundColor="#150207" translucent />
      <SafeAreaView style={styles.fullScreenContainer}>
        {/* Top Header / Caller Type Badge */}
        <View style={styles.topHeader}>
          <View style={styles.statusPill}>
            <View style={styles.pulsingLiveDot} />
            <Text style={styles.statusPillText}>
              {isQueue
                ? `طابور اتصال: ${incomingCall.queueName || "المبيعات"}`
                : isTransfer
                ? `تحويل وارد ${incomingCall.transferredBy ? `من ${incomingCall.transferredBy}` : ""}`
                : isRingBack
                ? "استرجاع مكالمة (لم يتم الرد على التحويل)"
                : "مكالمة واردة..."}
            </Text>
          </View>
        </View>

        {/* Center Caller Profile */}
        <View style={styles.centerProfile}>
          {/* Animated Avatar Rings */}
          <View style={styles.avatarRingOuter}>
            <View style={styles.avatarRingMiddle}>
              <View style={styles.avatarCircle}>
                <Ionicons name="person" size={54} color="#f5f0e8" />
              </View>
            </View>
          </View>

          {/* Caller Name & Details */}
          <Text style={styles.callerName} numberOfLines={2}>
            {incomingCall.callerName}
          </Text>

          <Text style={styles.callerSub}>
            {incomingCall.callerDepartment
              ? `${incomingCall.callerDepartment} • تحويلة #${incomingCall.callerExtension || "داخلي"}`
              : `تحويلة #${incomingCall.callerExtension || "داخلي"}`}
          </Text>

          {/* Protocol / HD Voice Badge */}
          <View style={styles.protocolBadge}>
            <Ionicons name="shield-checkmark" size={13} color="#4ade80" />
            <Text style={styles.protocolText}>WebRTC HD Voice • مشفر وفوري</Text>
          </View>
        </View>

        {/* Bottom Call Actions */}
        <View style={styles.bottomActions}>
          {/* Decline Button */}
          <View style={styles.actionCol}>
            <TouchableOpacity
              style={[styles.bigCallBtn, styles.declineBtn]}
              onPress={declineCall}
              activeOpacity={0.8}
            >
              <Ionicons
                name="call"
                size={34}
                color="#ffffff"
                style={{ transform: [{ rotate: "135deg" }] }}
              />
            </TouchableOpacity>
            <Text style={styles.actionLabel}>رفض المكالمة</Text>
          </View>

          {/* Answer Button */}
          <View style={styles.actionCol}>
            <TouchableOpacity
              style={[styles.bigCallBtn, styles.answerBtn]}
              onPress={answerCall}
              activeOpacity={0.8}
            >
              <Ionicons name="call" size={34} color="#ffffff" />
            </TouchableOpacity>
            <Text style={styles.actionLabel}>رد (قبول)</Text>
          </View>
        </View>
      </SafeAreaView>
    </Modal>
  );
};

const styles = StyleSheet.create({
  fullScreenContainer: {
    flex: 1,
    backgroundColor: "#150207",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 24,
    paddingTop: Platform.OS === "android" ? (StatusBar.currentHeight || 24) + 16 : 20,
    paddingBottom: 48,
  },
  topHeader: {
    width: "100%",
    alignItems: "center",
    marginTop: 10,
  },
  statusPill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(139, 29, 54, 0.45)",
    borderWidth: 1,
    borderColor: "rgba(245, 240, 232, 0.2)",
    paddingVertical: 8,
    paddingHorizontal: 18,
    borderRadius: 24,
    gap: 8,
  },
  pulsingLiveDot: {
    width: 9,
    height: 9,
    borderRadius: 4.5,
    backgroundColor: "#22c55e",
  },
  statusPillText: {
    color: "#f5f0e8",
    fontSize: 13,
    fontWeight: "600",
  },
  centerProfile: {
    alignItems: "center",
    width: "100%",
    marginVertical: "auto",
  },
  avatarRingOuter: {
    width: 170,
    height: 170,
    borderRadius: 85,
    backgroundColor: "rgba(139, 29, 54, 0.15)",
    borderWidth: 1.5,
    borderColor: "rgba(139, 29, 54, 0.35)",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 26,
  },
  avatarRingMiddle: {
    width: 140,
    height: 140,
    borderRadius: 70,
    backgroundColor: "rgba(139, 29, 54, 0.25)",
    borderWidth: 1.5,
    borderColor: "rgba(139, 29, 54, 0.6)",
    alignItems: "center",
    justifyContent: "center",
  },
  avatarCircle: {
    width: 110,
    height: 110,
    borderRadius: 55,
    backgroundColor: "#8b1d36",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#8b1d36",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.6,
    shadowRadius: 18,
    elevation: 12,
  },
  callerName: {
    color: "#ffffff",
    fontSize: 30,
    fontWeight: "bold",
    textAlign: "center",
    marginBottom: 8,
    paddingHorizontal: 16,
  },
  callerSub: {
    color: "rgba(245, 240, 232, 0.75)",
    fontSize: 16,
    textAlign: "center",
    marginBottom: 18,
  },
  protocolBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(255, 255, 255, 0.08)",
    paddingVertical: 5,
    paddingHorizontal: 14,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.12)",
  },
  protocolText: {
    color: "rgba(245, 240, 232, 0.85)",
    fontSize: 11,
    fontWeight: "500",
  },
  bottomActions: {
    flexDirection: "row",
    justifyContent: "space-around",
    alignItems: "center",
    width: "100%",
    paddingHorizontal: 20,
    marginBottom: 16,
  },
  actionCol: {
    alignItems: "center",
    gap: 12,
  },
  bigCallBtn: {
    width: 78,
    height: 78,
    borderRadius: 39,
    alignItems: "center",
    justifyContent: "center",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.5,
    shadowRadius: 14,
    elevation: 10,
  },
  declineBtn: {
    backgroundColor: "#ef4444",
    shadowColor: "#ef4444",
  },
  answerBtn: {
    backgroundColor: "#22c55e",
    shadowColor: "#22c55e",
  },
  actionLabel: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "600",
  },
});
