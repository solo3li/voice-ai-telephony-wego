import React, { useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet, TextInput, Linking, Platform } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Colors } from "../constants/theme";
import { useCall } from "../context/CallContext";
import { useAuthStore } from "../stores/useAuthStore";
import { AutoStartGuideModal } from "./AutoStartGuideModal";

export const DialpadView: React.FC = () => {
  const { dialpadInput, setDialpadInput, startCall } = useCall();
  const employee = useAuthStore((s) => s.employee);
  const [autoStartModalVisible, setAutoStartModalVisible] = useState(false);

  const keys = [
    { num: "1", sub: "" },
    { num: "2", sub: "ABC" },
    { num: "3", sub: "DEF" },
    { num: "4", sub: "GHI" },
    { num: "5", sub: "JKL" },
    { num: "6", sub: "MNO" },
    { num: "7", sub: "PQRS" },
    { num: "8", sub: "TUV" },
    { num: "9", sub: "WXYZ" },
    { num: "*", sub: "" },
    { num: "0", sub: "+" },
    { num: "#", sub: "" },
  ];

  const handleKeyPress = (num: string) => {
    setDialpadInput(dialpadInput + num);
  };

  const handleBackspace = () => {
    setDialpadInput(dialpadInput.slice(0, -1));
  };

  return (
    <View style={styles.container}>
      {/* 24/7 Always-on Softphone Banner */}
      <TouchableOpacity
        style={styles.batteryPill}
        onPress={() => setAutoStartModalVisible(true)}
        activeOpacity={0.8}
      >
        <Ionicons name="shield-checkmark" size={13} color="#10b981" />
        <Text style={styles.batteryPillText}>
          الخدمة تعمل في الخلفية (24/7) • اضغط لضبط توفير الطاقة
        </Text>
        <Ionicons name="chevron-forward" size={11} color={Colors.textMuted} />
      </TouchableOpacity>

      {/* Phone Number Display */}
      <View style={styles.displayRow}>
        <TextInput
          style={styles.numberInput}
          value={dialpadInput}
          onChangeText={setDialpadInput}
          placeholder="رقم التحويلة أو الطابور..."
          placeholderTextColor={Colors.textSubtle}
          keyboardType="phone-pad"
        />
        {dialpadInput.length > 0 && (
          <TouchableOpacity onPress={handleBackspace} style={styles.backspaceBtn}>
            <Ionicons name="backspace-outline" size={22} color={Colors.textMuted} />
          </TouchableOpacity>
        )}
      </View>

      {/* Quick AI Test Call Button (Owner / Supervisor Only) */}
      {employee?.is_owner && (
        <TouchableOpacity
          style={styles.aiTestButton}
          onPress={() => startCall("000", "المساعد الذكي (تجربة)")}
          activeOpacity={0.8}
        >
          <Ionicons name="sparkles" size={16} color="#10b981" style={{ marginRight: 6 }} />
          <Text style={styles.aiTestButtonText}>🤖 تجربة المساعد الذكي (مالك / مشرف)</Text>
          <Ionicons name="call" size={14} color="#10b981" style={{ marginLeft: 6 }} />
        </TouchableOpacity>
      )}

      {/* Speed Dial Queues */}
      <View style={styles.quickQueuesRow}>
        <TouchableOpacity
          style={styles.quickQueueChip}
          onPress={() => startCall("200", "طابور المبيعات")}
        >
          <Text style={styles.quickQueueText}>📞 طابور المبيعات (200)</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.quickQueueChip}
          onPress={() => startCall("102", "سارة (دعم)")}
        >
          <Text style={styles.quickQueueText}>👤 سارة (102)</Text>
        </TouchableOpacity>
      </View>

      {/* Dialpad 3x4 Grid */}
      <View style={styles.grid}>
        {keys.map((k) => (
          <TouchableOpacity
            key={k.num}
            style={styles.keyButton}
            onPress={() => handleKeyPress(k.num)}
            activeOpacity={0.6}
          >
            <Text style={styles.keyNumber}>{k.num}</Text>
            {k.sub ? <Text style={styles.keySub}>{k.sub}</Text> : null}
          </TouchableOpacity>
        ))}
      </View>

      {/* Call Button */}
      <View style={styles.bottomCallRow}>
        <TouchableOpacity
          style={styles.callActionButton}
          onPress={() => startCall()}
          activeOpacity={0.8}
        >
          <Ionicons name="call" size={24} color="#fff" />
        </TouchableOpacity>
      </View>

      <AutoStartGuideModal
        visible={autoStartModalVisible}
        onClose={() => setAutoStartModalVisible(false)}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 10,
    justifyContent: "space-between",
    paddingBottom: 16,
    backgroundColor: Colors.background,
  },
  batteryPill: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "rgba(16, 185, 129, 0.08)",
    borderWidth: 1,
    borderColor: "rgba(16, 185, 129, 0.25)",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 7,
    marginBottom: 8,
  },
  batteryPillText: {
    color: Colors.textMuted,
    fontSize: 10.5,
    fontWeight: "500",
    flex: 1,
    marginHorizontal: 6,
    textAlign: "right",
  },
  displayRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
    paddingHorizontal: 16,
    height: 48,
    marginBottom: 8,
  },
  numberInput: {
    flex: 1,
    color: Colors.textPrimary,
    fontSize: 18,
    fontWeight: "bold",
    letterSpacing: 1,
  },
  backspaceBtn: {
    padding: 4,
  },
  aiTestButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(16, 185, 129, 0.12)",
    borderWidth: 1,
    borderColor: "rgba(16, 185, 129, 0.35)",
    borderRadius: 10,
    paddingVertical: 8,
    paddingHorizontal: 12,
    marginBottom: 8,
  },
  aiTestButtonText: {
    color: "#10b981",
    fontSize: 13,
    fontWeight: "bold",
  },
  quickQueuesRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 10,
  },
  quickQueueChip: {
    backgroundColor: Colors.primaryBg,
    borderWidth: 1,
    borderColor: Colors.primaryBorder,
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 20,
  },
  quickQueueText: {
    color: Colors.primary,
    fontSize: 11,
    fontWeight: "600",
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    rowGap: 10,
  },
  keyButton: {
    width: "30%",
    aspectRatio: 1.3,
    backgroundColor: Colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
    alignItems: "center",
    justifyContent: "center",
  },
  keyNumber: {
    color: Colors.textPrimary,
    fontSize: 20,
    fontWeight: "bold",
  },
  keySub: {
    color: Colors.textMuted,
    fontSize: 9,
    fontWeight: "600",
    letterSpacing: 1,
    marginTop: 1,
  },
  bottomCallRow: {
    alignItems: "center",
    marginTop: 6,
  },
  callActionButton: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: Colors.liveGreen,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: Colors.liveGreen,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 10,
    elevation: 4,
  },
});
