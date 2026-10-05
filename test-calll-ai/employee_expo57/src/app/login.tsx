import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Platform,
  Image,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Colors } from "../constants/theme";
import { useAuthStore } from "../stores/useAuthStore";
import { useCallStore } from "../stores/useCallStore";

export default function LoginScreen() {
  const router = useRouter();
  const { login, isLoading, error, clearError } = useAuthStore();
  const initSignaling = useCallStore((s) => s.initSignaling);

  const [identifier, setIdentifier] = useState("101");
  const [password, setPassword] = useState("password123");
  const [showPassword, setShowPassword] = useState(false);

  const handleLogin = async () => {
    if (!identifier.trim() || !password.trim()) return;
    const success = await login(identifier.trim(), password.trim());
    if (success) {
      initSignaling();
      router.replace("/");
    }
  };

  const setDemoUser = (ext: string) => {
    clearError();
    setIdentifier(ext);
    setPassword("password123");
  };

  return (
    <View style={styles.container}>
      {/* Background Glow */}
      <View style={styles.glowCircle} />

      <View style={styles.card}>
        {/* Header / Brand */}
        <View style={styles.header}>
          <Image
            source={require("../../assets/images/logo.png")}
            style={styles.logoImage}
            resizeMode="contain"
          />
          <Text style={styles.title}>تسجيل دخول الموظف</Text>
          <Text style={styles.subtitle}>بوابة الاتصال الداخلي والمبيعات (WebRTC)</Text>
        </View>

        {/* Error Alert */}
        {error ? (
          <View style={styles.errorBox}>
            <Ionicons name="alert-circle-outline" size={18} color={Colors.endCallRed} />
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}

        {/* Inputs */}
        <View style={styles.form}>
          <View style={styles.inputGroup}>
            <Text style={styles.label}>رقم التحويلة أو اسم المستخدم</Text>
            <View style={styles.inputWrapper}>
              <Ionicons name="person-outline" size={18} color={Colors.textMuted} style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                value={identifier}
                onChangeText={(val) => {
                  clearError();
                  setIdentifier(val);
                }}
                placeholder="مثال: 101 أو ahmed"
                placeholderTextColor={Colors.textSubtle}
                autoCapitalize="none"
                editable={!isLoading}
              />
            </View>
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>كلمة المرور</Text>
            <View style={styles.inputWrapper}>
              <Ionicons name="lock-closed-outline" size={18} color={Colors.textMuted} style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                value={password}
                onChangeText={(val) => {
                  clearError();
                  setPassword(val);
                }}
                placeholder="كلمة المرور"
                placeholderTextColor={Colors.textSubtle}
                secureTextEntry={!showPassword}
                editable={!isLoading}
                onSubmitEditing={handleLogin}
              />
              <TouchableOpacity
                onPress={() => setShowPassword(!showPassword)}
                style={styles.eyeBtn}
              >
                <Ionicons
                  name={showPassword ? "eye-off-outline" : "eye-outline"}
                  size={18}
                  color={Colors.textMuted}
                />
              </TouchableOpacity>
            </View>
          </View>

          {/* Submit Button */}
          <TouchableOpacity
            style={[styles.loginBtn, isLoading && styles.loginBtnDisabled]}
            onPress={handleLogin}
            disabled={isLoading}
          >
            {isLoading ? (
              <ActivityIndicator color="#0d141e" size="small" />
            ) : (
              <>
                <Text style={styles.loginBtnText}>دخول للنظام</Text>
                <Ionicons name="arrow-forward" size={18} color="#0d141e" />
              </>
            )}
          </TouchableOpacity>
        </View>

        {/* Quick Demo Accounts */}
        <View style={styles.demoSection}>
          <Text style={styles.demoTitle}>حسابات تجريبية سريعة:</Text>
          <View style={styles.chipRow}>
            <TouchableOpacity
              style={[styles.chip, identifier === "101" && styles.chipActive]}
              onPress={() => setDemoUser("101")}
            >
              <Text style={[styles.chipText, identifier === "101" && styles.chipTextActive]}>
                101 أحمد (مبيعات)
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.chip, identifier === "102" && styles.chipActive]}
              onPress={() => setDemoUser("102")}
            >
              <Text style={[styles.chipText, identifier === "102" && styles.chipTextActive]}>
                102 سارة (دعم)
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.chip, identifier === "103" && styles.chipActive]}
              onPress={() => setDemoUser("103")}
            >
              <Text style={[styles.chipText, identifier === "103" && styles.chipTextActive]}>
                103 محمد (مبيعات)
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
    justifyContent: "center",
    alignItems: "center",
    padding: 16,
  },
  glowCircle: {
    position: "absolute",
    width: 320,
    height: 320,
    borderRadius: 160,
    backgroundColor: "rgba(0, 196, 180, 0.08)",
    top: "15%",
    alignSelf: "center",
  },
  card: {
    width: "100%",
    maxWidth: 420,
    backgroundColor: Colors.card,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
    padding: 28,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.4,
    shadowRadius: 20,
    elevation: 8,
  },
  header: {
    alignItems: "center",
    marginBottom: 24,
  },
  logoImage: {
    width: 80,
    height: 80,
    borderRadius: 20,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
  },
  title: {
    fontSize: 22,
    fontWeight: "700",
    color: Colors.textWhite,
    marginBottom: 6,
  },
  subtitle: {
    fontSize: 13,
    color: Colors.textMuted,
    textAlign: "center",
  },
  errorBox: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Colors.endCallRedBg,
    borderWidth: 1,
    borderColor: "rgba(239, 68, 68, 0.4)",
    borderRadius: 10,
    padding: 12,
    marginBottom: 18,
    gap: 8,
  },
  errorText: {
    color: "#fca5a5",
    fontSize: 13,
    flex: 1,
    textAlign: "right",
  },
  form: {
    gap: 16,
  },
  inputGroup: {
    gap: 6,
  },
  label: {
    fontSize: 13,
    fontWeight: "500",
    color: Colors.textMuted,
    textAlign: "right",
  },
  inputWrapper: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Colors.cardSubtle,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
    borderRadius: 12,
    paddingHorizontal: 12,
    height: 48,
  },
  inputIcon: {
    marginRight: 8,
  },
  input: {
    flex: 1,
    color: Colors.textWhite,
    fontSize: 15,
    textAlign: "right",
    outlineStyle: "none" as any,
  },
  eyeBtn: {
    padding: 4,
  },
  loginBtn: {
    backgroundColor: Colors.primaryTeal,
    height: 48,
    borderRadius: 12,
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    gap: 8,
    marginTop: 8,
  },
  loginBtnDisabled: {
    opacity: 0.6,
  },
  loginBtnText: {
    color: "#0d141e",
    fontSize: 15,
    fontWeight: "700",
  },
  demoSection: {
    marginTop: 24,
    paddingTop: 18,
    borderTopWidth: 1,
    borderTopColor: Colors.cardBorder,
    alignItems: "center",
  },
  demoTitle: {
    fontSize: 12,
    color: Colors.textSubtle,
    marginBottom: 10,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: 8,
  },
  chip: {
    backgroundColor: Colors.cardSubtle,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 16,
  },
  chipActive: {
    borderColor: Colors.primaryTeal,
    backgroundColor: Colors.primaryTealBg,
  },
  chipText: {
    fontSize: 12,
    color: Colors.textMuted,
  },
  chipTextActive: {
    color: Colors.primaryTeal,
    fontWeight: "600",
  },
});
