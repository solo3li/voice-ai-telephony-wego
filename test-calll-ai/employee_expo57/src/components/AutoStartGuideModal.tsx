import React from "react";
import {
  Modal,
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Linking,
  Platform,
  ScrollView,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Colors } from "../constants/theme";

interface AutoStartGuideModalProps {
  visible: boolean;
  onClose: () => void;
}

export const AutoStartGuideModal: React.FC<AutoStartGuideModalProps> = ({
  visible,
  onClose,
}) => {
  const handleOpenSettings = async () => {
    try {
      if (Platform.OS === "android") {
        await Linking.openSettings();
      }
    } catch (e) {
      console.warn("Could not open settings:", e);
    }
  };

  return (
    <Modal
      visible={visible}
      animationType="fade"
      transparent
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <View style={styles.modalCard}>
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.iconCircle}>
              <Ionicons name="shield-checkmark" size={28} color="#10b981" />
            </View>
            <Text style={styles.title}>حماية الاتصال الدائم (24/7)</Text>
            <Text style={styles.subtitle}>
              خطوات سريعة لضمان استقبال المكالمات حتى لو كان التطبيق مغلقاً أو الشاشة مطفأة
            </Text>
          </View>

          <ScrollView style={styles.stepsList} showsVerticalScrollIndicator={false}>
            {/* Step 1 */}
            <View style={styles.stepItem}>
              <View style={styles.stepNumberBadge}>
                <Text style={styles.stepNumberText}>1</Text>
              </View>
              <View style={styles.stepContent}>
                <Text style={styles.stepTitle}>التشغيل التلقائي (Auto-start)</Text>
                <Text style={styles.stepDesc}>
                  اسمح للتطبيق بالتشغيل التلقائي عند فتح الهاتف أو في الخلفية.
                </Text>
              </View>
            </View>

            {/* Step 2 */}
            <View style={styles.stepItem}>
              <View style={styles.stepNumberBadge}>
                <Text style={styles.stepNumberText}>2</Text>
              </View>
              <View style={styles.stepContent}>
                <Text style={styles.stepTitle}>إلغاء قيود توفير الطاقة</Text>
                <Text style={styles.stepDesc}>
                  اضبط خيار تحسين البطارية على "بلا قيود" (No Restrictions) حتى لا يوقف نظام أندرويد الخدمة.
                </Text>
              </View>
            </View>

            {/* Step 3 */}
            <View style={styles.stepItem}>
              <View style={styles.stepNumberBadge}>
                <Text style={styles.stepNumberText}>3</Text>
              </View>
              <View style={styles.stepContent}>
                <Text style={styles.stepTitle}>تثبيت التطبيق في المهام الأخيرة</Text>
                <Text style={styles.stepDesc}>
                  في شاشة التطبيقات المفتوحة (Recent Apps)، اسحب التطبيق لأسفل واضغط على رمز القفل 🔒 لتأمينه.
                </Text>
              </View>
            </View>

            {/* Step 4 */}
            <View style={styles.stepItem}>
              <View style={styles.stepNumberBadge}>
                <Text style={styles.stepNumberText}>4</Text>
              </View>
              <View style={styles.stepContent}>
                <Text style={styles.stepTitle}>إذن الظهور فوق التطبيقات</Text>
                <Text style={styles.stepDesc}>
                  يسمح لشاشة المكالمة بالظهور الفوري والرنين حتى لو كنت تستخدم تطبيقاً آخر.
                </Text>
              </View>
            </View>
          </ScrollView>

          {/* Action Buttons */}
          <View style={styles.buttonContainer}>
            <TouchableOpacity
              style={styles.openSettingsBtn}
              onPress={handleOpenSettings}
              activeOpacity={0.8}
            >
              <Ionicons name="settings-outline" size={18} color="#fff" style={{ marginRight: 8 }} />
              <Text style={styles.openSettingsBtnText}>فتح إعدادات التطبيق الآن</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.closeBtn}
              onPress={onClose}
              activeOpacity={0.7}
            >
              <Text style={styles.closeBtnText}>حسناً، التطبيق جاهز ومحمي</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.65)",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 20,
  },
  modalCard: {
    width: "100%",
    maxWidth: 420,
    backgroundColor: "#18181b",
    borderRadius: 20,
    padding: 24,
    maxHeight: "85%",
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.1)",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.5,
    shadowRadius: 20,
    elevation: 10,
  },
  header: {
    alignItems: "center",
    marginBottom: 18,
  },
  iconCircle: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: "rgba(16, 185, 129, 0.15)",
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 12,
  },
  title: {
    fontSize: 18,
    fontWeight: "bold",
    color: "#fff",
    textAlign: "center",
    marginBottom: 6,
  },
  subtitle: {
    fontSize: 13,
    color: Colors.textMuted,
    textAlign: "center",
    lineHeight: 18,
  },
  stepsList: {
    marginVertical: 10,
  },
  stepItem: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 14,
    backgroundColor: "rgba(255, 255, 255, 0.03)",
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.05)",
  },
  stepNumberBadge: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: "#8b1d36",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 12,
    marginTop: 2,
  },
  stepNumberText: {
    color: "#fff",
    fontSize: 12,
    fontWeight: "bold",
  },
  stepContent: {
    flex: 1,
  },
  stepTitle: {
    fontSize: 14,
    fontWeight: "600",
    color: "#fff",
    marginBottom: 3,
  },
  stepDesc: {
    fontSize: 12,
    color: Colors.textMuted,
    lineHeight: 16,
  },
  buttonContainer: {
    marginTop: 16,
    gap: 10,
  },
  openSettingsBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#8b1d36",
    paddingVertical: 14,
    borderRadius: 12,
  },
  openSettingsBtnText: {
    color: "#fff",
    fontSize: 15,
    fontWeight: "bold",
  },
  closeBtn: {
    paddingVertical: 10,
    alignItems: "center",
  },
  closeBtnText: {
    color: Colors.textMuted,
    fontSize: 13,
  },
});
