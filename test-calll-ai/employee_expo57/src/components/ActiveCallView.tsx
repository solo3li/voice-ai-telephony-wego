import React from "react";
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from "react-native";
import { Ionicons, FontAwesome5 } from "@expo/vector-icons";
import { Colors } from "../constants/theme";
import { useCall } from "../context/CallContext";

export const ActiveCallView: React.FC = () => {
  const {
    callState,
    activeCall,
    isMuted,
    isOnHold,
    toggleMute,
    toggleHold,
    endCall,
    setTransferModalVisible,
    sendWhatsAppOrSms,
  } = useCall();

  const formatTime = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  // ── Render 1: HOLD Screen (Shown to Caller / Employee 1 while waiting for transfer) ──
  if (callState === "HOLD") {
    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.contentContainer} bounces={false}>
        <View style={styles.topStatusRow}>
          <Text style={styles.activeCallLabel}>قيد الانتظار</Text>
          <View style={[styles.liveBadge, { backgroundColor: "rgba(128, 0, 32, 0.1)" }]}>
            <Text style={styles.liveDot}>((•))</Text>
            <Text style={styles.liveText}>Hold</Text>
          </View>
        </View>

        <View style={styles.specialCard}>
          <View style={[styles.specialIconCircle, { backgroundColor: "rgba(128, 0, 32, 0.08)" }]}>
            <Ionicons name="musical-notes" size={36} color={Colors.primary} />
          </View>

          <Text style={styles.specialTitle}>جاري تحويل مكالمتك</Text>
          <Text style={styles.specialSubtitle}>يرجى الانتظار، سيقوم الزميل بالرد عليك خلال لحظات...</Text>

          <View style={styles.timerRow}>
            <Ionicons name="time-outline" size={16} color={Colors.primary} />
            <Text style={styles.timerText}>{formatTime(activeCall.durationSeconds)}</Text>
          </View>

          <View style={[styles.infoNoteBox, { backgroundColor: "rgba(22, 163, 74, 0.08)" }]}>
            <Ionicons name="volume-high-outline" size={16} color={Colors.liveGreen} />
            <Text style={[styles.infoNoteText, { color: Colors.liveGreen }]}>
              نغمة الانتظار تعمل في الخلفية...
            </Text>
          </View>

          <TouchableOpacity style={styles.endCallSpecialBtn} onPress={endCall} activeOpacity={0.8}>
            <Ionicons name="call" size={18} color="#fff" style={{ transform: [{ rotate: "135deg" }] }} />
            <Text style={styles.endCallSpecialBtnText}>إنهاء المكالمة</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    );
  }

  // ── Render 3: Standard CONNECTED / Active Call Screen ──
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.contentContainer} bounces={false}>
      {/* 1. Header: Active Call Status & Live Badge */}
      <View style={styles.topStatusRow}>
        <Text style={styles.activeCallLabel}>مكالمة جارية</Text>
        <View style={styles.liveBadge}>
          <Text style={styles.liveDot}>((•))</Text>
          <Text style={styles.liveText}>مباشر</Text>
        </View>
      </View>

      {/* 2. Caller Information */}
      <View style={styles.callerInfoSection}>
        <Text style={styles.callerName}>{activeCall.callerName || "مكالمة WebRTC"}</Text>
        <Text style={styles.callerPhone}>{activeCall.phoneNumber}</Text>

        <View style={styles.timerRow}>
          <Ionicons name="time-outline" size={15} color={Colors.primary} />
          <Text style={styles.timerText}>{formatTime(activeCall.durationSeconds)}</Text>
        </View>
      </View>

      {/* 3. Call Controls */}
      <View style={styles.controlsRow}>
        {/* Mute */}
        <View style={styles.controlCol}>
          <TouchableOpacity
            style={[styles.roundButton, isMuted && styles.roundButtonActiveMute]}
            onPress={toggleMute}
            activeOpacity={0.7}
          >
            <Ionicons
              name={isMuted ? "mic-off" : "mic"}
              size={24}
              color={isMuted ? Colors.endCallRed : Colors.primary}
            />
          </TouchableOpacity>
          <Text style={[styles.controlLabel, isMuted && { color: Colors.endCallRed }]}>
            {isMuted ? "كتم الصوت" : "كتم"}
          </Text>
        </View>

        {/* Hold */}
        <View style={styles.controlCol}>
          <TouchableOpacity
            style={[styles.roundButton, isOnHold && styles.roundButtonActiveHold]}
            onPress={toggleHold}
            activeOpacity={0.7}
          >
            <Ionicons
              name={isOnHold ? "play" : "pause"}
              size={24}
              color={isOnHold ? Colors.holdAmber : Colors.primary}
            />
          </TouchableOpacity>
          <Text style={[styles.controlLabel, isOnHold && { color: Colors.holdAmber }]}>
            {isOnHold ? "معلّق" : "تعليق"}
          </Text>
        </View>

        {/* Transfer */}
        <View style={styles.controlCol}>
          <TouchableOpacity
            style={styles.roundButton}
            onPress={() => setTransferModalVisible(true)}
            activeOpacity={0.7}
          >
            <Ionicons name="shuffle-outline" size={24} color={Colors.primary} />
          </TouchableOpacity>
          <Text style={styles.controlLabel}>تحويل</Text>
        </View>

        {/* End Call */}
        <View style={styles.controlCol}>
          <TouchableOpacity style={styles.endCallButton} onPress={endCall} activeOpacity={0.7}>
            <Ionicons name="call" size={24} color="#fff" style={{ transform: [{ rotate: "135deg" }] }} />
          </TouchableOpacity>
          <Text style={[styles.controlLabel, { color: Colors.endCallRed }]}>إنهاء</Text>
        </View>
      </View>

      {/* 4. Live AI / Call Info Card */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={styles.cardTitleGroup}>
            <Ionicons name="sparkles" size={16} color={Colors.primary} />
            <Text style={styles.cardTitle}>بيانات المكالمة الحالية</Text>
          </View>
          <View style={styles.sentimentBadge}>
            <Text style={styles.sentimentText}>{activeCall.sentiment}</Text>
          </View>
        </View>

        <View style={styles.summaryList}>
          {activeCall.summaryBullets.map((bullet, idx) => (
            <View key={idx} style={styles.summaryBulletRow}>
              <View style={styles.bulletDot} />
              <Text style={styles.summaryText}>{bullet}</Text>
            </View>
          ))}
        </View>
      </View>

      {/* 5. Quick Actions */}
      <View style={styles.quickActionsSection}>
        <Text style={styles.quickActionsHeader}>إجراءات سريعة</Text>
        <View style={styles.quickActionsGrid}>
          <TouchableOpacity style={styles.quickActionBtn} onPress={sendWhatsAppOrSms} activeOpacity={0.7}>
            <FontAwesome5 name="whatsapp" size={16} color={Colors.primary} />
            <Text style={styles.quickActionText}>مراسلة واتساب</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.quickActionBtn} activeOpacity={0.7}>
            <Ionicons name="document-text-outline" size={16} color={Colors.primary} />
            <Text style={styles.quickActionText}>إضافة ملاحظة</Text>
          </TouchableOpacity>
        </View>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  contentContainer: {
    padding: 16,
    paddingBottom: 32,
  },
  topStatusRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  activeCallLabel: {
    color: Colors.textMuted,
    fontSize: 13,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  liveBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Colors.liveBadgeBg,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    gap: 5,
  },
  liveDot: {
    color: Colors.liveGreen,
    fontSize: 10,
    fontWeight: "bold",
  },
  liveText: {
    color: Colors.liveGreen,
    fontSize: 12,
    fontWeight: "600",
  },
  callerInfoSection: {
    alignItems: "center",
    marginBottom: 24,
  },
  callerName: {
    color: Colors.textPrimary,
    fontSize: 22,
    fontWeight: "bold",
    marginBottom: 4,
    textAlign: "center",
  },
  callerPhone: {
    color: Colors.textMuted,
    fontSize: 14,
    marginBottom: 8,
  },
  timerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: Colors.surface,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  timerText: {
    color: Colors.primary,
    fontSize: 14,
    fontWeight: "600",
  },
  controlsRow: {
    flexDirection: "row",
    justifyContent: "space-around",
    alignItems: "center",
    marginBottom: 24,
    paddingHorizontal: 8,
  },
  controlCol: {
    alignItems: "center",
    gap: 6,
  },
  roundButton: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },
  roundButtonActiveMute: {
    backgroundColor: "rgba(220, 38, 38, 0.1)",
    borderColor: Colors.endCallRed,
  },
  roundButtonActiveHold: {
    backgroundColor: "rgba(217, 119, 6, 0.1)",
    borderColor: Colors.holdAmber,
  },
  endCallButton: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: Colors.endCallRed,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: Colors.endCallRed,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
  },
  controlLabel: {
    color: Colors.textSecondary,
    fontSize: 11,
    fontWeight: "500",
  },
  card: {
    backgroundColor: Colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
    padding: 16,
    marginBottom: 16,
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 1,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  cardTitleGroup: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  cardTitle: {
    color: Colors.textPrimary,
    fontSize: 14,
    fontWeight: "bold",
  },
  sentimentBadge: {
    backgroundColor: Colors.primaryBg,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: Colors.primaryBorder,
  },
  sentimentText: {
    color: Colors.primary,
    fontSize: 11,
    fontWeight: "600",
  },
  summaryList: {
    gap: 8,
  },
  summaryBulletRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
  },
  bulletDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Colors.primary,
    marginTop: 6,
  },
  summaryText: {
    color: Colors.textSecondary,
    fontSize: 13,
    lineHeight: 18,
    flex: 1,
  },
  quickActionsSection: {
    marginTop: 4,
  },
  quickActionsHeader: {
    color: Colors.textMuted,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 10,
  },
  quickActionsGrid: {
    flexDirection: "row",
    gap: 10,
  },
  quickActionBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingVertical: 12,
    borderRadius: 10,
  },
  quickActionText: {
    color: Colors.textPrimary,
    fontSize: 12,
    fontWeight: "600",
  },

  // ── Special State Card Styles (Transferring / Hold) ──
  specialCard: {
    backgroundColor: Colors.card,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: 24,
    alignItems: "center",
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.08,
    shadowRadius: 16,
    elevation: 3,
    marginTop: 10,
  },
  specialIconCircle: {
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: Colors.primaryFade,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
    borderWidth: 1,
    borderColor: Colors.borderLight,
  },
  specialTitle: {
    fontSize: 20,
    fontWeight: "bold",
    color: Colors.textPrimary,
    marginBottom: 6,
    textAlign: "center",
  },
  specialSubtitle: {
    fontSize: 13,
    color: Colors.textMuted,
    textAlign: "center",
    marginBottom: 16,
    lineHeight: 18,
    maxWidth: 280,
  },
  infoNoteBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: Colors.primaryFade,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 10,
    marginVertical: 18,
    width: "100%",
  },
  infoNoteText: {
    fontSize: 12,
    color: Colors.textSecondary,
    flex: 1,
    lineHeight: 16,
  },
  cancelTransferBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: Colors.endCallRed,
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 12,
    width: "100%",
    shadowColor: Colors.endCallRed,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 3,
  },
  cancelTransferBtnText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "700",
  },
  endCallSpecialBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: Colors.endCallRed,
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 12,
    width: "100%",
  },
  endCallSpecialBtnText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "700",
  },
});
