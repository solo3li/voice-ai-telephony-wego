import React, { useEffect } from "react";
import { View, Text, StyleSheet, Modal, TouchableOpacity, ScrollView } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Colors } from "../constants/theme";
import { useCall } from "../context/CallContext";
import { useDirectoryStore } from "../stores/useDirectoryStore";

export const TransferModal: React.FC = () => {
  const { transferModalVisible, setTransferModalVisible, transferCall } = useCall();
  const { queues, employees, fetchDirectory } = useDirectoryStore();

  useEffect(() => {
    if (transferModalVisible) {
      fetchDirectory();
    }
  }, [transferModalVisible]);

  return (
    <Modal
      visible={transferModalVisible}
      transparent
      animationType="fade"
      onRequestClose={() => setTransferModalVisible(false)}
    >
      <View style={styles.backdrop}>
        <View style={styles.modalCard}>
          {/* Modal Header */}
          <View style={styles.modalHeader}>
            <View style={styles.headerLeft}>
              <View style={styles.iconCircle}>
                <Ionicons name="shuffle-outline" size={18} color={Colors.primary} />
              </View>
              <Text style={styles.modalTitle}>تحويل المكالمة</Text>
            </View>
            <TouchableOpacity onPress={() => setTransferModalVisible(false)} style={styles.closeBtn}>
              <Ionicons name="close" size={20} color={Colors.textMuted} />
            </TouchableOpacity>
          </View>

          <Text style={styles.subtitle}>
            اختر طابوراً أو زميلاً متاحاً لتحويل المكالمة إليه:
          </Text>

          {/* 1. Dynamic Queues / Departments */}
          {queues && queues.length > 0 && (
            <View style={styles.sectionBlock}>
              <Text style={styles.sectionHeader}>طوابير الاتصال (توزيع تلقائي):</Text>
              <View style={styles.quickQueuesRow}>
                {queues.map((q) => (
                  <TouchableOpacity
                    key={q.id}
                    style={styles.queueBtn}
                    onPress={() => transferCall(q.code, q.name)}
                    activeOpacity={0.7}
                  >
                    <Ionicons name="layers-outline" size={14} color={Colors.primary} style={{ marginBottom: 2 }} />
                    <Text style={styles.queueBtnText} numberOfLines={1}>{q.name}</Text>
                    <Text style={styles.queueCodeText}>كود: {q.code}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          )}

          {/* 2. Colleagues list */}
          <View style={styles.sectionBlock}>
            <Text style={styles.sectionHeader}>الزملاء (أولوية مباشرة ثم الكيو):</Text>
            <ScrollView style={styles.agentList} showsVerticalScrollIndicator={false}>
              {employees && employees.length > 0 ? (
                employees.map((emp) => {
                  const isAvailable = emp.status === "ready";
                  const statusColor = isAvailable
                    ? Colors.liveGreen
                    : emp.status === "busy"
                    ? Colors.endCallRed
                    : Colors.holdAmber;
                  const statusText = isAvailable
                    ? "متاح"
                    : emp.status === "busy"
                    ? "مشغول"
                    : emp.status === "break"
                    ? "استراحة"
                    : "غير متصل";

                  return (
                    <TouchableOpacity
                      key={emp.id}
                      style={[styles.agentRow, !isAvailable && styles.agentRowDisabled]}
                      disabled={!isAvailable}
                      onPress={() => transferCall(emp.extension, emp.display_name)}
                      activeOpacity={0.7}
                    >
                      <View style={styles.agentInfo}>
                        <Text style={styles.agentName}>{emp.display_name}</Text>
                        <Text style={styles.agentRole}>
                          {emp.department || "المبيعات"} (تحويلة: {emp.extension})
                        </Text>
                      </View>

                      <View style={styles.statusGroup}>
                        <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
                        <Text style={[styles.statusLabel, { color: statusColor }]}>
                          {statusText}
                        </Text>
                      </View>
                    </TouchableOpacity>
                  );
                })
              ) : (
                <Text style={styles.emptyText}>لا يوجد زملاء متاحون حالياً</Text>
              )}
            </ScrollView>
          </View>

          {/* Cancel Button */}
          <TouchableOpacity
            style={styles.cancelButton}
            onPress={() => setTransferModalVisible(false)}
            activeOpacity={0.7}
          >
            <Text style={styles.cancelText}>إلغاء</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(44, 10, 18, 0.65)",
    alignItems: "center",
    justifyContent: "center",
    padding: 20,
  },
  modalCard: {
    width: "100%",
    maxWidth: 380,
    backgroundColor: Colors.card,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: 20,
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.18,
    shadowRadius: 20,
    elevation: 10,
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  iconCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: Colors.primaryFade,
    alignItems: "center",
    justifyContent: "center",
  },
  modalTitle: {
    color: Colors.textPrimary,
    fontSize: 16,
    fontWeight: "bold",
  },
  closeBtn: {
    padding: 4,
  },
  subtitle: {
    color: Colors.textMuted,
    fontSize: 12,
    marginBottom: 14,
    lineHeight: 18,
  },
  sectionBlock: {
    marginBottom: 14,
  },
  sectionHeader: {
    fontSize: 11,
    fontWeight: "700",
    color: Colors.primary,
    marginBottom: 6,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  quickQueuesRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  queueBtn: {
    flex: 1,
    minWidth: 140,
    backgroundColor: Colors.primaryFade,
    borderWidth: 1,
    borderColor: Colors.borderLight,
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderRadius: 10,
    alignItems: "center",
  },
  queueBtnText: {
    color: Colors.primary,
    fontSize: 12,
    fontWeight: "700",
  },
  queueCodeText: {
    color: Colors.textMuted,
    fontSize: 10,
    marginTop: 2,
  },
  agentList: {
    maxHeight: 180,
  },
  agentRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderLight,
  },
  agentRowDisabled: {
    opacity: 0.45,
  },
  agentInfo: {
    flex: 1,
  },
  agentName: {
    color: Colors.textPrimary,
    fontSize: 13,
    fontWeight: "600",
  },
  agentRole: {
    color: Colors.textMuted,
    fontSize: 11,
    marginTop: 2,
  },
  statusGroup: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  statusDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
  },
  statusLabel: {
    fontSize: 11,
    fontWeight: "600",
  },
  emptyText: {
    fontSize: 12,
    color: Colors.textMuted,
    textAlign: "center",
    paddingVertical: 12,
  },
  cancelButton: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingVertical: 10,
    borderRadius: 10,
    alignItems: "center",
    marginTop: 4,
  },
  cancelText: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: "600",
  },
});
