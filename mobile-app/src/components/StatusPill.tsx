import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useApp } from '../state/AppContext';
import { colors, radius } from '../theme';

const LABEL: Record<string, { text: string; color: string; bg: string }> = {
  connected: { text: 'Connected', color: '#146B34', bg: colors.greenSoft },
  connecting: { text: 'Connecting…', color: '#8A5A00', bg: colors.yellowSoft },
  reconnecting: { text: 'Reconnecting…', color: '#8A5A00', bg: colors.yellowSoft },
  unreachable: { text: "Can't reach PC", color: '#C0392B', bg: colors.redSoft },
  rejected: { text: 'Re-pair needed', color: '#C0392B', bg: colors.redSoft },
  idle: { text: 'Offline', color: colors.muted, bg: colors.bgDeep },
};

export function StatusPill() {
  const { status, pairing, reconnect } = useApp();
  const l = LABEL[status] ?? LABEL.idle;
  return (
    <Pressable onPress={status === 'connected' ? undefined : reconnect} style={[styles.pill, { backgroundColor: l.bg }]} accessibilityLabel={`Connection: ${l.text}`}>
      <View style={[styles.dot, { backgroundColor: l.color }]} />
      <Text style={[styles.text, { color: l.color }]} numberOfLines={1}>
        {status === 'connected' && pairing ? pairing.pcName : l.text}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pill: { flexDirection: 'row', alignItems: 'center', borderRadius: radius.pill, paddingHorizontal: 12, paddingVertical: 6, maxWidth: 190 },
  dot: { width: 8, height: 8, borderRadius: 4, marginRight: 6 },
  text: { fontSize: 13, fontWeight: '700' },
});
