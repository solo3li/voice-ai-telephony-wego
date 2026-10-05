import React, { useState } from "react";
import { View, Text, StyleSheet, Platform, StatusBar, TouchableOpacity, Image } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Colors } from "../constants/theme";
import { useAuthStore } from "../stores/useAuthStore";
import { useCallStore } from "../stores/useCallStore";

interface WindowFrameProps {
  children: React.ReactNode;
}

export const WindowFrame: React.FC<WindowFrameProps> = ({ children }) => {
  const isWeb = Platform.OS === "web";
  const insets = useSafeAreaInsets();
  const topInset = isWeb ? 0 : Math.max(insets.top, Platform.OS === "android" ? (StatusBar.currentHeight || 24) : 0);

  const { employee, updateStatus, logout } = useAuthStore();
  const disconnectSignaling = useCallStore((s) => s.disconnectSignaling);

  const [statusMenuOpen, setStatusMenuOpen] = useState(false);

  const handleLogout = () => {
    disconnectSignaling();
    logout();
  };

  const getStatusColor = (status?: string) => {
    switch (status) {
      case "ready":   return Colors.liveGreen;
      case "break":   return Colors.holdAmber;
      case "busy":    return Colors.endCallRed;
      default:        return Colors.textSubtle;
    }
  };

  const getStatusLabel = (status?: string) => {
    switch (status) {
      case "ready":   return "متاح";
      case "break":   return "استراحة";
      case "busy":    return "مشغول";
      default:        return "غير متصل";
    }
  };

  return (
    <View style={styles.outerContainer}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.background} />
      <View style={[styles.windowContainer, isWeb && styles.webCardContainer]}>
        {/* Window title bar */}
        <View style={[styles.windowHeader, !isWeb && { paddingTop: topInset, height: 44 + topInset }]}>
          {/* Mac window dots & Brand Logo */}
          <View style={styles.dotsRow}>
            <View style={[styles.dot, { backgroundColor: Colors.dotRed }]} />
            <View style={[styles.dot, { backgroundColor: Colors.dotYellow }]} />
            <View style={[styles.dot, { backgroundColor: Colors.dotGreen }]} />
            <Image
              source={require("../../assets/images/logo.png")}
              style={styles.headerLogo}
              resizeMode="contain"
            />
          </View>

          {/* Logged in Employee Info */}
          {employee ? (
            <View style={styles.employeeHeaderInfo}>
              {/* Status Pill Toggle */}
              <TouchableOpacity
                style={styles.statusPill}
                onPress={() => setStatusMenuOpen(!statusMenuOpen)}
                activeOpacity={0.8}
              >
                <View style={[styles.statusIndicatorDot, { backgroundColor: getStatusColor(employee.status) }]} />
                <Text style={styles.statusText}>{getStatusLabel(employee.status)}</Text>
                <Ionicons name="chevron-down" size={12} color={Colors.textMuted} />
              </TouchableOpacity>

              {/* Employee Name & Ext */}
              <View style={styles.employeeBadge}>
                <Text style={styles.employeeName} numberOfLines={1}>
                  {employee.is_owner ? "👑 " : ""}{employee.display_name}
                </Text>
                <Text style={styles.employeeExt}>#{employee.extension}</Text>
              </View>

              {/* Logout Button */}
              <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
                <Ionicons name="log-out-outline" size={16} color={Colors.textMuted} />
              </TouchableOpacity>
            </View>
          ) : (
            <Text style={styles.appTitle}>WebRTC Softphone</Text>
          )}
        </View>

        {/* Status Dropdown Menu */}
        {statusMenuOpen && (
          <View style={[styles.statusDropdown, !isWeb && { top: 48 + topInset }]}>
            <TouchableOpacity style={styles.dropdownOption} onPress={() => { updateStatus("ready"); setStatusMenuOpen(false); }}>
              <View style={[styles.statusIndicatorDot, { backgroundColor: Colors.liveGreen }]} />
              <Text style={styles.dropdownOptionText}>🟢 متاح (جاهز لاستقبال المكالمات)</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.dropdownOption} onPress={() => { updateStatus("break"); setStatusMenuOpen(false); }}>
              <View style={[styles.statusIndicatorDot, { backgroundColor: Colors.holdAmber }]} />
              <Text style={styles.dropdownOptionText}>🟡 استراحة (إيقاف رنين الطابور)</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.dropdownOption} onPress={() => { updateStatus("busy"); setStatusMenuOpen(false); }}>
              <View style={[styles.statusIndicatorDot, { backgroundColor: Colors.endCallRed }]} />
              <Text style={styles.dropdownOptionText}>🔴 مشغول (في اجتماع أو مكالمة)</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Inner Content */}
        <View style={styles.contentArea}>{children}</View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  outerContainer: {
    flex: 1,
    backgroundColor: "#d8cfc4",
    alignItems: "center",
    justifyContent: "center",
  },
  windowContainer: {
    flex: 1,
    width: "100%",
    backgroundColor: Colors.background,
    overflow: "hidden",
  },
  webCardContainer: {
    maxWidth: 410,
    height: 770,
    maxHeight: "98%",
    borderRadius: 20,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
    shadowColor: "#5c0016",
    shadowOffset: { width: 0, height: 16 },
    shadowOpacity: 0.18,
    shadowRadius: 32,
    elevation: 20,
  },
  windowHeader: {
    height: 44,
    paddingHorizontal: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: Colors.card,
    borderBottomWidth: 1,
    borderBottomColor: Colors.cardBorder,
    zIndex: 10,
  },
  dotsRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  headerLogo: {
    width: 24,
    height: 24,
    borderRadius: 6,
    marginLeft: 6,
  },
  appTitle: {
    fontSize: 12,
    color: Colors.textMuted,
    fontWeight: "500",
  },
  employeeHeaderInfo: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  statusPill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Colors.cardSubtle,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
    gap: 5,
  },
  statusIndicatorDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  statusText: {
    fontSize: 11,
    color: Colors.textPrimary,
    fontWeight: "600",
  },
  employeeBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: Colors.primaryBg,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: Colors.primaryBorder,
  },
  employeeName: {
    fontSize: 11,
    fontWeight: "700",
    color: Colors.primary,
    maxWidth: 90,
  },
  employeeExt: {
    fontSize: 10,
    color: Colors.primaryDark,
    fontWeight: "600",
  },
  logoutBtn: {
    padding: 5,
    borderRadius: 6,
    backgroundColor: Colors.cardSubtle,
  },
  statusDropdown: {
    position: "absolute",
    top: 48,
    right: 14,
    backgroundColor: Colors.card,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
    borderRadius: 12,
    paddingVertical: 6,
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 16,
    zIndex: 999,
    width: 250,
  },
  dropdownOption: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 9,
    gap: 8,
  },
  dropdownOptionText: {
    fontSize: 12,
    color: Colors.textPrimary,
    fontWeight: "500",
  },
  contentArea: {
    flex: 1,
  },
});
