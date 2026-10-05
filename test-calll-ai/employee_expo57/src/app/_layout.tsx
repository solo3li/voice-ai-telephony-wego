import React, { useEffect } from "react";
import { Platform, AppState, AppStateStatus } from "react-native";
import { Stack, useRouter, useSegments } from "expo-router";
import { CallProvider } from "../context/CallContext";
import { useAuthStore } from "../stores/useAuthStore";
import { useCallStore } from "../stores/useCallStore";

if (Platform.OS !== "web") {
  try {
    const { registerGlobals } = require("@livekit/react-native");
    registerGlobals();
  } catch (e) {
    console.warn("LiveKit registerGlobals note:", e);
  }
}

import { notificationService } from "../services/notificationService";
import { watchdogService } from "../services/watchdogService";

function AuthGate({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isRestoring, restoreSession } = useAuthStore();
  const initSignaling = useCallStore((s) => s.initSignaling);
  const checkActiveIncomingCall = useCallStore((s) => s.checkActiveIncomingCall);
  const router = useRouter();
  const segments = useSegments();

  useEffect(() => {
    restoreSession().then(() => {
      const auth = useAuthStore.getState();
      if (auth.isAuthenticated) {
        initSignaling();
        checkActiveIncomingCall();
        watchdogService.start();
        notificationService.registerForPushNotifications();
        if (auth.employee) {
          notificationService.startPersistentServiceNotification(auth.employee.display_name, auth.employee.extension);
        }
      }
    });

    const subscription = AppState.addEventListener("change", (nextAppState: AppStateStatus) => {
      if (nextAppState === "active") {
        const auth = useAuthStore.getState();
        if (auth.isAuthenticated) {
          initSignaling();
          checkActiveIncomingCall();
          watchdogService.start();
          if (auth.employee) {
            notificationService.startPersistentServiceNotification(auth.employee.display_name, auth.employee.extension);
          }
        }
      }
    });

    return () => {
      subscription.remove();
    };
  }, []);

  useEffect(() => {
    if (isRestoring) return;
    const inLogin = segments[0] === "login";
    if (!isAuthenticated && !inLogin) {
      router.replace("/login");
      watchdogService.stop();
      notificationService.stopPersistentServiceNotification();
    } else if (isAuthenticated && inLogin) {
      router.replace("/");
      watchdogService.start();
      notificationService.registerForPushNotifications();
      const auth = useAuthStore.getState();
      if (auth.employee) {
        notificationService.startPersistentServiceNotification(auth.employee.display_name, auth.employee.extension);
      }
    }
  }, [isAuthenticated, isRestoring, segments]);

  return <>{children}</>;
}

import { SafeAreaProvider } from "react-native-safe-area-context";

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <CallProvider>
        <AuthGate>
          <Stack screenOptions={{ headerShown: false }} />
        </AuthGate>
      </CallProvider>
    </SafeAreaProvider>
  );
}

