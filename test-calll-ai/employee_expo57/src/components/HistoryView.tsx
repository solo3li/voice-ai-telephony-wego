import React, { useState, useEffect, useCallback } from "react";
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  TextInput, ActivityIndicator, RefreshControl
} from "react-native";
import { Ionicons, Feather } from "@expo/vector-icons";
import { Colors } from "../constants/theme";
import { apiRequest } from "../constants/api";
import { useAuthStore } from "../stores/useAuthStore";
import { useCallStore } from "../stores/useCallStore";

// ── Types ──────────────────────────────────────────────────────────────────
interface CallLogEntry {
  id: number;
  other_party: string;
  extension: string;
  room_name: string;
  call_type: "inbound" | "outbound" | "missed" | "transfer";
  started_at: string;
  ended_at: string | null;
  duration_secs: number;
}

// ── Helpers ─────────────────────────────────────────────────────────────────
function formatDuration(secs: number): string {
  if (!secs || secs < 1) return "0s";
  if (secs < 60) return `${secs}s`;
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function formatTimestamp(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return "الآن";
    if (diffMins < 60) return `منذ ${diffMins} د`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `منذ ${diffHours} س`;
    return d.toLocaleDateString("ar-EG", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return dateStr;
  }
}

const CALL_TYPE_CONFIG: Record<string, { label: string; icon: any; color: string; bg: string }> = {
  inbound:  { label: "وارد",    icon: "phone-incoming", color: Colors.liveGreen,   bg: Colors.liveGreenBg },
  outbound: { label: "صادر",    icon: "phone-outgoing", color: Colors.primary,     bg: Colors.primaryBg },
  missed:   { label: "فائت",    icon: "phone-missed",   color: Colors.endCallRed,  bg: Colors.endCallRedBg },
  transfer: { label: "محول",    icon: "phone-forwarded",color: Colors.holdAmber,   bg: Colors.holdAmberBg },
};

// ── Component ────────────────────────────────────────────────────────────────
export const HistoryView: React.FC = () => {
  const token = useAuthStore((s) => s.token);
  const startCall = useCallStore((s) => s.startCall);

  const [logs, setLogs] = useState<CallLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "missed" | "inbound" | "outbound">("all");

  const fetchLogs = useCallback(async (silent = false) => {
    if (!token) return;
    if (!silent) setIsLoading(true);
    setError(null);
    try {
      const data = await apiRequest<{ status: string; logs: CallLogEntry[] }>(
        "/api/call-center/calls/logs/",
        { method: "GET" },
        token
      );
      if (data.status === "success") {
        setLogs(data.logs || []);
      }
    } catch (err: any) {
      setError("فشل تحميل سجل المكالمات");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [token]);

  // Fetch on mount
  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  // Re-fetch when a new call ends (listen to callState changes)
  const callState = useCallStore((s) => s.callState);
  useEffect(() => {
    if (callState === "IDLE") {
      // Small delay to let the backend finish logging
      const t = setTimeout(() => fetchLogs(true), 1500);
      return () => clearTimeout(t);
    }
  }, [callState, fetchLogs]);

  const filtered = logs.filter((log) => {
    if (filter !== "all" && log.call_type !== filter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return log.other_party.toLowerCase().includes(q) || log.extension.includes(q);
    }
    return true;
  });

  const renderItem = ({ item }: { item: CallLogEntry }) => {
    const cfg = CALL_TYPE_CONFIG[item.call_type] || CALL_TYPE_CONFIG.outbound;

    return (
      <View style={styles.card}>
        {/* Left: icon */}
        <View style={[styles.typeIconBox, { backgroundColor: cfg.bg }]}>
          <Feather name={cfg.icon} size={16} color={cfg.color} />
        </View>

        {/* Middle: info */}
        <View style={styles.cardBody}>
          <View style={styles.cardTopRow}>
            <Text style={styles.partyName} numberOfLines={1}>{item.other_party || "—"}</Text>
            <Text style={styles.timestamp}>{formatTimestamp(item.started_at)}</Text>
          </View>
          <View style={styles.cardBottomRow}>
            <Text style={[styles.callTypeBadge, { color: cfg.color }]}>{cfg.label}</Text>
            {item.extension ? <Text style={styles.extText}>#{item.extension}</Text> : null}
            <View style={styles.durationRow}>
              <Feather name="clock" size={10} color={Colors.textSubtle} />
              <Text style={styles.durationText}>{formatDuration(item.duration_secs)}</Text>
            </View>
          </View>
        </View>

        {/* Right: callback button */}
        {item.extension ? (
          <TouchableOpacity
            style={styles.callbackBtn}
            onPress={() => startCall(item.extension, item.other_party)}
            activeOpacity={0.8}
          >
            <Ionicons name="call" size={14} color="#fff" />
          </TouchableOpacity>
        ) : null}
      </View>
    );
  };

  return (
    <View style={styles.container}>
      {/* Search */}
      <View style={styles.searchBar}>
        <Feather name="search" size={15} color={Colors.textSubtle} style={{ marginRight: 8 }} />
        <TextInput
          style={styles.searchInput}
          placeholder="بحث عن اسم أو تحويلة..."
          placeholderTextColor={Colors.textSubtle}
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
        {searchQuery.length > 0 && (
          <TouchableOpacity onPress={() => setSearchQuery("")}>
            <Feather name="x" size={14} color={Colors.textMuted} />
          </TouchableOpacity>
        )}
      </View>

      {/* Filter tabs */}
      <View style={styles.filterRow}>
        {(["all", "inbound", "outbound", "missed"] as const).map((f) => (
          <TouchableOpacity
            key={f}
            style={[styles.filterTab, filter === f && styles.filterTabActive]}
            onPress={() => setFilter(f)}
          >
            <Text style={[styles.filterText, filter === f && styles.filterTextActive]}>
              {f === "all" ? "الكل" : f === "inbound" ? "وارد" : f === "outbound" ? "صادر" : "فائت"}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Content */}
      {isLoading && logs.length === 0 ? (
        <ActivityIndicator color={Colors.primary} style={{ marginTop: 40 }} />
      ) : error ? (
        <View style={styles.errorBox}>
          <Feather name="wifi-off" size={24} color={Colors.endCallRed} />
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={() => fetchLogs()}>
            <Text style={styles.retryText}>إعادة المحاولة</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(item) => item.id.toString()}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={isRefreshing}
              onRefresh={() => { setIsRefreshing(true); fetchLogs(); }}
              tintColor={Colors.primary}
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyBox}>
              <Feather name="phone-off" size={28} color={Colors.textSubtle} />
              <Text style={styles.emptyText}>لا توجد مكالمات مسجلة بعد</Text>
            </View>
          }
        />
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
    paddingHorizontal: 14,
    paddingTop: 12,
  },
  searchBar: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Colors.card,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
    paddingHorizontal: 12,
    height: 38,
    marginBottom: 10,
  },
  searchInput: {
    flex: 1,
    color: Colors.textPrimary,
    fontSize: 13,
    textAlign: "right",
  },
  filterRow: {
    flexDirection: "row",
    borderBottomWidth: 1,
    borderBottomColor: Colors.cardBorder,
    marginBottom: 12,
  },
  filterTab: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 8,
  },
  filterTabActive: {
    borderBottomWidth: 2,
    borderBottomColor: Colors.primary,
  },
  filterText: {
    color: Colors.textMuted,
    fontSize: 12,
    fontWeight: "500",
  },
  filterTextActive: {
    color: Colors.primary,
    fontWeight: "bold",
  },
  listContent: {
    gap: 8,
    paddingBottom: 20,
  },
  card: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
    padding: 12,
    gap: 10,
  },
  typeIconBox: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  cardBody: {
    flex: 1,
    gap: 4,
  },
  cardTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  partyName: {
    color: Colors.textPrimary,
    fontSize: 13,
    fontWeight: "700",
    flex: 1,
  },
  timestamp: {
    color: Colors.textSubtle,
    fontSize: 10,
    marginLeft: 6,
  },
  cardBottomRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  callTypeBadge: {
    fontSize: 11,
    fontWeight: "600",
  },
  extText: {
    color: Colors.textMuted,
    fontSize: 11,
  },
  durationRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    marginLeft: "auto",
  },
  durationText: {
    color: Colors.textSubtle,
    fontSize: 10,
  },
  callbackBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: Colors.primary,
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  errorBox: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
  },
  errorText: {
    color: Colors.textMuted,
    fontSize: 13,
    textAlign: "center",
  },
  retryBtn: {
    backgroundColor: Colors.primaryBg,
    borderWidth: 1,
    borderColor: Colors.primaryBorder,
    paddingHorizontal: 16,
    paddingVertical: 7,
    borderRadius: 8,
  },
  retryText: {
    color: Colors.primary,
    fontSize: 12,
    fontWeight: "600",
  },
  emptyBox: {
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    marginTop: 40,
  },
  emptyText: {
    color: Colors.textSubtle,
    fontSize: 13,
    textAlign: "center",
  },
});
