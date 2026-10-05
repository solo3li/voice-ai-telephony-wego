import { Platform } from "react-native";
import { createAudioPlayer, setAudioModeAsync, AudioPlayer } from "expo-audio";
import * as Haptics from "expo-haptics";

// High quality phone sounds
const INCOMING_RINGTONE_URL = "https://assets.mixkit.co/active_storage/sfx/1359/1359-preview.mp3";
const OUTGOING_RINGBACK_URL = "https://assets.mixkit.co/active_storage/sfx/2874/2874-preview.mp3";

class SoundService {
  private incomingPlayer: AudioPlayer | null = null;
  private outgoingPlayer: AudioPlayer | null = null;
  private hapticsInterval: any = null;
  private webAudioCtx: any = null;
  private webOscGain: any = null;
  private isRingingIncoming = false;
  private isRingingOutgoing = false;

  constructor() {
    this.configureAudioMode();
  }

  private async configureAudioMode() {
    if (Platform.OS !== "web") {
      try {
        await setAudioModeAsync({
          playsInSilentMode: true,
          shouldPlayInBackground: true,
        });
      } catch (e) {
        console.log("[SoundService] configureAudioMode note:", e);
      }
    }
  }

  // ==================== Web Audio Tone Synthesizers ====================

  private startWebTone(freq1: number, freq2: number, onDuration: number, offDuration: number) {
    if (Platform.OS !== "web" || typeof window === "undefined") return;
    try {
      this.stopWebTone();
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioCtx) return;
      this.webAudioCtx = new AudioCtx();
      if (this.webAudioCtx.state === "suspended") {
        this.webAudioCtx.resume();
      }

      const osc1 = this.webAudioCtx.createOscillator();
      const osc2 = this.webAudioCtx.createOscillator();
      const gainNode = this.webAudioCtx.createGain();

      osc1.frequency.value = freq1;
      osc2.frequency.value = freq2;

      osc1.connect(gainNode);
      osc2.connect(gainNode);
      gainNode.connect(this.webAudioCtx.destination);

      const now = this.webAudioCtx.currentTime;
      gainNode.gain.setValueAtTime(0, now);

      const cycle = onDuration + offDuration;
      for (let i = 0; i < 30; i++) {
        const start = now + (i * cycle);
        gainNode.gain.setValueAtTime(0.12, start);
        gainNode.gain.setValueAtTime(0, start + onDuration);
      }

      osc1.start(now);
      osc2.start(now);
      this.webOscGain = { osc1, osc2, gainNode };
    } catch (e) {
      console.log("[SoundService] Web audio tone error:", e);
    }
  }

  private stopWebTone() {
    if (this.webOscGain) {
      try {
        this.webOscGain.osc1.stop();
        this.webOscGain.osc2.stop();
        this.webOscGain.osc1.disconnect();
        this.webOscGain.osc2.disconnect();
      } catch (e) {}
      this.webOscGain = null;
    }
    if (this.webAudioCtx) {
      try {
        this.webAudioCtx.close();
      } catch (e) {}
      this.webAudioCtx = null;
    }
  }

  // ==================== Incoming Ringtone ====================

  async playIncomingRingtone() {
    if (this.isRingingIncoming) return;
    this.stopAll();
    this.isRingingIncoming = true;

    // 1. Repeated vibration on mobile
    if (Platform.OS !== "web") {
      try {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        this.hapticsInterval = setInterval(() => {
          Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
        }, 1200);
      } catch (e) {
        console.log("[SoundService] Haptics error:", e);
      }
    }

    // 2. Play Audio Ringtone
    if (Platform.OS === "web") {
      this.startWebTone(440, 480, 1.5, 2.0);
    } else {
      try {
        const player = createAudioPlayer(INCOMING_RINGTONE_URL);
        player.loop = true;
        player.volume = 1.0;
        player.play();
        this.incomingPlayer = player;
      } catch (e) {
        console.warn("[SoundService] Failed to play incoming sound:", e);
      }
    }
  }

  // ==================== Outgoing Ringback Tone ====================

  async playOutgoingRingback() {
    if (this.isRingingOutgoing) return;
    this.stopAll();
    this.isRingingOutgoing = true;

    if (Platform.OS === "web") {
      this.startWebTone(400, 450, 1.2, 2.5);
    } else {
      try {
        const player = createAudioPlayer(OUTGOING_RINGBACK_URL);
        player.loop = true;
        player.volume = 0.6;
        player.play();
        this.outgoingPlayer = player;
      } catch (e) {
        console.warn("[SoundService] Failed to play outgoing sound:", e);
      }
    }
  }

  // ==================== Stop All ====================

  async stopAll() {
    this.isRingingIncoming = false;
    this.isRingingOutgoing = false;

    // Stop haptics
    if (this.hapticsInterval) {
      clearInterval(this.hapticsInterval);
      this.hapticsInterval = null;
    }

    // Stop Web Audio
    this.stopWebTone();

    // Stop Native Incoming Sound
    if (this.incomingPlayer) {
      const p = this.incomingPlayer;
      this.incomingPlayer = null;
      try {
        p.pause();
        p.remove();
      } catch (e) {}
    }

    // Stop Native Outgoing Sound
    if (this.outgoingPlayer) {
      const p = this.outgoingPlayer;
      this.outgoingPlayer = null;
      try {
        p.pause();
        p.remove();
      } catch (e) {}
    }
  }
}

export const soundService = new SoundService();
