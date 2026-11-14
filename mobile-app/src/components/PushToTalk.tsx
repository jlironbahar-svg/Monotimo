import { RecordingPresets, requestRecordingPermissionsAsync, setAudioModeAsync, useAudioRecorder, type RecordingOptions } from 'expo-audio';
import { File } from 'expo-file-system';
import { useEffect, useRef, useState } from 'react';
import { Animated, Easing, Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { stopVoice } from '../lib/voice';
import { useApp } from '../state/AppContext';
import { colors, shadow } from '../theme';
import { useAnimValue } from '../lib/anim';

// Mono AAC at 64 kbps: small uploads, plenty for speech recognition.
const OPTIONS: RecordingOptions = { ...RecordingPresets.HIGH_QUALITY, numberOfChannels: 1, bitRate: 64000 };
const MIN_MS = 400;
const MAX_MS = 60_000;

async function readBase64(uri: string): Promise<string> {
  try {
    return await new File(uri).base64();
  } catch {
    // web: the recorder returns a blob: URL
    const blob = await (await fetch(uri)).blob();
    return await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '');
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });
  }
}

type Phase = 'idle' | 'starting' | 'recording' | 'stopping';

/** Hold to talk. The recording is sent to the PC, which transcribes it with Groq Whisper. */
export function PushToTalk({ disabled, size = 96 }: { disabled?: boolean; size?: number }) {
  const { sendVoice, sfx, tap, showToast } = useApp();
  const recorder = useAudioRecorder(OPTIONS);
  const [recording, setRecording] = useState(false);
  const phase = useRef<Phase>('idle');
  const releaseRequested = useRef(false);
  const startedAt = useRef(0);
  const maxTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pulse = useAnimValue(0);

  useEffect(() => {
    if (!recording) {
      pulse.stopAnimation();
      pulse.setValue(0);
      return;
    }
    const loop = Animated.loop(Animated.timing(pulse, { toValue: 1, duration: 1100, easing: Easing.out(Easing.quad), useNativeDriver: true }));
    loop.start();
    return () => loop.stop();
  }, [recording, pulse]);

  const finish = async (send: boolean) => {
    if (phase.current !== 'recording') return;
    phase.current = 'stopping';
    if (maxTimer.current) clearTimeout(maxTimer.current);
    setRecording(false);
    try {
      await recorder.stop();
    } catch {
      /* already stopped */
    }
    await setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true }).catch(() => undefined);
    sfx('recStop');
    const elapsed = Date.now() - startedAt.current;
    phase.current = 'idle';
    if (!send) return;
    if (elapsed < MIN_MS) {
      showToast('Hold the button while you talk 🎤');
      return;
    }
    const uri = recorder.uri;
    if (!uri) {
      showToast("Couldn't record audio", 'error');
      return;
    }
    try {
      const b64 = await readBase64(uri);
      sendVoice(b64, Platform.OS === 'web' ? 'audio/webm' : 'audio/m4a');
    } catch {
      showToast("Couldn't read the recording", 'error');
    }
  };

  const start = async () => {
    if (disabled || phase.current !== 'idle') return;
    phase.current = 'starting';
    releaseRequested.current = false;
    try {
      const perm = await requestRecordingPermissionsAsync();
      if (!perm.granted) {
        phase.current = 'idle';
        showToast('Allow microphone access to talk to your friend', 'error');
        return;
      }
      stopVoice();
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      startedAt.current = Date.now();
      phase.current = 'recording';
      setRecording(true);
      tap();
      sfx('recStart');
      maxTimer.current = setTimeout(() => void finish(true), MAX_MS);
      if (releaseRequested.current) void finish(true); // finger lifted while we were starting
    } catch (e) {
      phase.current = 'idle';
      showToast(`Microphone error: ${e instanceof Error ? e.message : String(e)}`, 'error');
    }
  };

  const release = () => {
    if (phase.current === 'starting') releaseRequested.current = true;
    else void finish(true);
  };

  return (
    <View style={styles.wrap}>
      <View style={{ width: size * 1.6, height: size * 1.6, alignItems: 'center', justifyContent: 'center' }}>
        {recording && (
          <Animated.View
            style={[
              styles.ring,
              {
                width: size,
                height: size,
                borderRadius: size / 2,
                opacity: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.5, 0] }),
                transform: [{ scale: pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.6] }) }],
              },
            ]}
          />
        )}
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Hold to talk"
          disabled={disabled}
          onPressIn={() => void start()}
          onPressOut={release}
          style={({ pressed }) => [
            styles.button,
            shadow,
            {
              width: size,
              height: size,
              borderRadius: size / 2,
              backgroundColor: recording ? colors.pink : colors.primary,
              opacity: disabled ? 0.45 : 1,
              transform: [{ scale: pressed || recording ? 1.08 : 1 }],
            },
          ]}
        >
          <Text style={{ fontSize: size * 0.4 }}>{recording ? '👂' : '🎤'}</Text>
        </Pressable>
      </View>
      <Text style={styles.hint}>{recording ? 'Listening… let go to send' : 'Hold to talk'}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center' },
  ring: { position: 'absolute', backgroundColor: colors.pink },
  button: { alignItems: 'center', justifyContent: 'center' },
  hint: { marginTop: -6, fontSize: 13, fontWeight: '700', color: colors.muted },
});
