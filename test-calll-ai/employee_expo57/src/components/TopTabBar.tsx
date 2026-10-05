import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { Ionicons, MaterialCommunityIcons } from "@expo/vector-icons";
import { Colors } from "../constants/theme";
import { useCall, TabKey } from "../context/CallContext";

export const TopTabBar: React.FC = () => {
  const { activeTab, setActiveTab } = useCall();

  const tabs: { key: TabKey; label: string; icon: any; badge?: number }[] = [
    { key: "dialpad",  label: "Dialpad",  icon: "dialpad" },
    { key: "history",  label: "History",  icon: "history", badge: 3 },
    { key: "contacts", label: "Contacts", icon: "contacts" },
  ];

  return (
    <View style={styles.tabBarContainer}>
      {tabs.map((tab) => {
        const isActive = activeTab === tab.key;
        return (
          <TouchableOpacity
            key={tab.key}
            style={[styles.tabItem, isActive && styles.activeTabItem]}
            onPress={() => setActiveTab(tab.key)}
            activeOpacity={0.7}
          >
            <View style={styles.iconWrapper}>
              {tab.key === "dialpad" && (
                <MaterialCommunityIcons
                  name="dialpad"
                  size={24}
                  color={isActive ? Colors.primary : Colors.textMuted}
                />
              )}
              {tab.key === "history" && (
                <Ionicons
                  name="time-outline"
                  size={24}
                  color={isActive ? Colors.primary : Colors.textMuted}
                />
              )}
              {tab.key === "contacts" && (
                <Ionicons
                  name="people-outline"
                  size={24}
                  color={isActive ? Colors.primary : Colors.textMuted}
                />
              )}

              {/* Badge indicator */}
              {tab.badge && (
                <View style={styles.badgeContainer}>
                  <Text style={styles.badgeText}>{tab.badge}</Text>
                </View>
              )}
            </View>

            <Text style={[styles.tabLabel, isActive ? styles.activeTabLabel : styles.inactiveTabLabel]}>
              {tab.label}
            </Text>

            {/* Bottom active indicator line */}
            {isActive && <View style={styles.activeIndicator} />}
          </TouchableOpacity>
        );
      })}
    </View>
  );
};

const styles = StyleSheet.create({
  tabBarContainer: {
    flexDirection: "row",
    height: 64,
    borderBottomWidth: 1,
    borderBottomColor: Colors.cardBorder,
    backgroundColor: Colors.card,
  },
  tabItem: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
    paddingTop: 4,
  },
  activeTabItem: {
    backgroundColor: Colors.primaryBg,
  },
  iconWrapper: {
    position: "relative",
    alignItems: "center",
    justifyContent: "center",
  },
  badgeContainer: {
    position: "absolute",
    top: -4,
    right: -10,
    backgroundColor: Colors.primary,
    width: 17,
    height: 17,
    borderRadius: 9,
    alignItems: "center",
    justifyContent: "center",
  },
  badgeText: {
    color: Colors.textWhite,
    fontSize: 10,
    fontWeight: "bold",
  },
  tabLabel: {
    fontSize: 12,
    marginTop: 4,
    fontWeight: "500",
  },
  activeTabLabel: {
    color: Colors.primary,
    fontWeight: "700",
  },
  inactiveTabLabel: {
    color: Colors.textMuted,
  },
  activeIndicator: {
    position: "absolute",
    bottom: 0,
    left: 12,
    right: 12,
    height: 2.5,
    backgroundColor: Colors.primary,
    borderRadius: 2,
  },
});
