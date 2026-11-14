import { CameraView, useCameraPermissions, type BarcodeScanningResult } from 'expo-camera';
import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { parsePairingPayload } from '../../../shared/protocol';
import { Puppy } from '../components/Puppy';
import { Card, PillButton } from '../components/ui';
import { useApp } from '../state/AppContext';
import { colors, font, radius } from '../theme';

/** First launch: scan the QR code shown by the PC agent. */
export function SetupScreen() {
  const insets = useSafeAreaInsets();
  const { pairWith, pairWithText, status, statusDetail, pairing, forgetPc, sfx, showToast } = useApp();
  const [permission, requestPermission] = useCameraPermissions();
  const [manual, setManual] = useState(false);
  const [code, setCode] = useState('');
  const lastScan = useRef('');

  const pending = !!pairing && !pairing.deviceToken;
  const failed = pending && (status === 'rejected' || status === 'unreachable');

  useEffect(() => {
    if (failed) sfx('error');
  }, [failed, sfx]);

  const onScan = ({ data }: BarcodeScanningResult) => {
    if (pending || data === lastScan.current) return;
    lastScan.current = data;
    const info = parsePairingPayload(data);
    if (!info) {
      showToast("That QR code isn't from Desktop Friend", 'error');
      return;
    }
    sfx('bark');
    pairWith(info);
  };

  const scanAgain = () => {
    lastScan.current = '';
    forgetPc();
  };

  const submitCode = () => {
    if (!pairWithText(code)) showToast('Paste the pairing link shown in the PC terminal (desktopfriend://pair?...)', 'error');
  };

  return (
    <LinearGradient colors={[colors.bg, colors.bgDeep]} style={{ flex: 1 }}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior="padding">
        <ScrollView contentContainerStyle={[styles.content, { paddingTop: insets.top + 24, paddingBottom: insets.bottom + 24 }]} keyboardShouldPersistTaps="handled">
          <View style={styles.hero}>
            <Puppy size={130} mood={failed ? 'sad' : pending ? 'curious' : 'happy'} onPress={() => sfx('bark')} />
          </View>
          <Text style={styles.title}>Set up Desktop Friend</Text>
          <Text style={styles.subtitle}>Your new buddy lives on this phone and helps out on your computer.</Text>

          <Card style={styles.steps}>
            <Step n={1} text="On your PC, run Desktop Friend (pc-agent/start.bat or start.sh)." />
            <Step n={2} text="Make sure this phone is on the same Wi-Fi as the PC." />
            <Step n={3} text="Scan the QR code in the Desktop Friend window." />
          </Card>

          {pending ? (
            <Card style={styles.connecting}>
              {failed ? (
                <>
                  <Text style={styles.connTitle}>{status === 'rejected' ? 'Pairing was refused' : `Can't reach ${pairing!.pcName}`}</Text>
                  <Text style={styles.connText}>
                    {statusDetail ||
                      'Check that Desktop Friend is running and both devices share the same Wi-Fi. Some routers block devices from talking to each other (guest networks / AP isolation).'}
                  </Text>
                  <PillButton label="Scan again" emoji="📷" onPress={scanAgain} style={{ marginTop: 12 }} />
                </>
              ) : (
                <>
                  <ActivityIndicator color={colors.primary} size="large" />
                  <Text style={styles.connTitle}>Saying hi to {pairing!.pcName}…</Text>
                  <Text style={styles.connText}>{pairing!.hosts.join(' · ')}</Text>
                  <PillButton label="Cancel" tone="soft" small onPress={scanAgain} style={{ marginTop: 12 }} />
                </>
              )}
            </Card>
          ) : (
            <View style={styles.scannerWrap}>
              {!permission ? (
                <ActivityIndicator color={colors.primary} />
              ) : permission.granted ? (
                <View style={styles.scanner}>
                  <CameraView
                    style={StyleSheet.absoluteFill}
                    facing="back"
                    barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
                    onBarcodeScanned={onScan}
                  />
                  <View style={styles.frame} pointerEvents="none">
                    {(['tl', 'tr', 'bl', 'br'] as const).map((c) => (
                      <View key={c} style={[styles.corner, cornerStyle(c)]} />
                    ))}
                  </View>
                  <Text style={styles.scanHint}>Point at the QR code on your PC</Text>
                </View>
              ) : (
                <Card style={{ alignItems: 'center' }}>
                  <Text style={styles.connTitle}>📷 Camera needed</Text>
                  <Text style={styles.connText}>Desktop Friend uses the camera only to scan the pairing QR code.</Text>
                  <PillButton label="Allow camera" onPress={() => void requestPermission()} style={{ marginTop: 12 }} />
                </Card>
              )}
            </View>
          )}

          {!pending && (
            <View style={{ marginTop: 16 }}>
              {manual ? (
                <Card>
                  <Text style={styles.label}>Pairing link</Text>
                  <TextInput
                    value={code}
                    onChangeText={setCode}
                    placeholder="desktopfriend://pair?v=1&h=192.168.1.20&p=8765&t=…"
                    placeholderTextColor={colors.faint}
                    autoCapitalize="none"
                    autoCorrect={false}
                    style={styles.input}
                    multiline
                  />
                  <PillButton label="Connect" onPress={submitCode} disabled={!code.trim()} style={{ marginTop: 10 }} />
                </Card>
              ) : (
                <PillButton label="No camera? Enter the code instead" tone="soft" small onPress={() => setManual(true)} />
              )}
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </LinearGradient>
  );
}

function Step({ n, text }: { n: number; text: string }) {
  return (
    <View style={styles.step}>
      <View style={styles.stepNum}>
        <Text style={styles.stepNumText}>{n}</Text>
      </View>
      <Text style={styles.stepText}>{text}</Text>
    </View>
  );
}

function cornerStyle(c: 'tl' | 'tr' | 'bl' | 'br') {
  const s = 5;
  return {
    top: c[0] === 't' ? 0 : undefined,
    bottom: c[0] === 'b' ? 0 : undefined,
    left: c[1] === 'l' ? 0 : undefined,
    right: c[1] === 'r' ? 0 : undefined,
    borderTopWidth: c[0] === 't' ? s : 0,
    borderBottomWidth: c[0] === 'b' ? s : 0,
    borderLeftWidth: c[1] === 'l' ? s : 0,
    borderRightWidth: c[1] === 'r' ? s : 0,
  };
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: 20 },
  hero: { alignItems: 'center' },
  title: { ...font.title, textAlign: 'center', marginTop: 4 },
  subtitle: { ...font.small, textAlign: 'center', marginTop: 6, marginBottom: 16, fontSize: 15 },
  steps: { paddingVertical: 10 },
  step: { flexDirection: 'row', alignItems: 'center', paddingVertical: 6 },
  stepNum: { width: 28, height: 28, borderRadius: 14, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  stepNumText: { color: '#fff', fontWeight: '800' },
  stepText: { flex: 1, fontSize: 14.5, color: colors.text },
  scannerWrap: { marginTop: 16, alignItems: 'center' },
  scanner: { width: '100%', aspectRatio: 1, borderRadius: radius.xl, overflow: 'hidden', backgroundColor: '#000', alignItems: 'center', justifyContent: 'flex-end' },
  frame: { position: 'absolute', top: '18%', left: '18%', right: '18%', bottom: '18%' },
  corner: { position: 'absolute', width: 36, height: 36, borderColor: '#fff', borderRadius: 6 },
  scanHint: { color: '#fff', fontWeight: '700', marginBottom: 14, backgroundColor: 'rgba(0,0,0,0.45)', paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill, overflow: 'hidden' },
  connecting: { marginTop: 16, alignItems: 'center', paddingVertical: 24 },
  connTitle: { ...font.h2, marginTop: 10, textAlign: 'center' },
  connText: { ...font.small, marginTop: 6, textAlign: 'center' },
  label: { fontSize: 13, fontWeight: '700', color: colors.muted, marginBottom: 6 },
  input: { borderRadius: radius.sm, backgroundColor: colors.bg, padding: 12, fontSize: 14, color: colors.text, minHeight: 60 },
});
