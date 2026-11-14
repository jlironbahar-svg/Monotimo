import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { useApp } from '../state/AppContext';
import { colors, radius } from '../theme';
import { Icon } from './ui';

/** Slim banner shown above every mode while the PC isn't connected, with a one-tap retry. */
export function ConnectionBanner() {
  const { status, statusDetail, pairing, reconnect } = useApp();
  if (status === 'connected' || !pairing) return null;
  const pc = pairing.pcName;
  const busy = status === 'connecting' || status === 'reconnecting';
  const text =
    status === 'rejected'
      ? statusDetail || `${pc} doesn't recognise this phone any more. Scan its QR code again in Settings.`
      : busy
        ? `Connecting to ${pc}…`
        : `Can't reach ${pc}. Is Desktop Friend running and on the same Wi-Fi?`;
  return (
    <Pressable onPress={busy ? undefined : reconnect} style={[styles.banner, busy ? styles.busy : styles.bad]} accessibilityRole="button" accessibilityLabel={text}>
      {busy ? <ActivityIndicator size="small" color="#8A5A00" /> : <Icon name="wifi-outline" size={18} color="#C0392B" />}
      <Text style={[styles.text, { color: busy ? '#8A5A00' : '#C0392B' }]} numberOfLines={2}>
        {text}
      </Text>
      {!busy && status !== 'rejected' ? (
        <View style={styles.retry}>
          <Text style={styles.retryText}>Retry</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  banner: { flexDirection: 'row', alignItems: 'center', gap: 10, marginHorizontal: 12, marginTop: 6, paddingHorizontal: 14, paddingVertical: 10, borderRadius: radius.md },
  busy: { backgroundColor: colors.yellowSoft },
  bad: { backgroundColor: colors.redSoft },
  text: { flex: 1, fontSize: 13, fontWeight: '700' },
  retry: { backgroundColor: '#fff', borderRadius: radius.pill, paddingHorizontal: 12, paddingVertical: 5 },
  retryText: { color: '#C0392B', fontWeight: '800', fontSize: 13 },
});
