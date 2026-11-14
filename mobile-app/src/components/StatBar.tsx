import { useEffect } from 'react';
import { Animated, StyleSheet, Text, View } from 'react-native';

import { colors, radius } from '../theme';
import { useAnimValue } from '../lib/anim';

export function StatBar({ emoji, label, value, color }: { emoji: string; label: string; value: number; color: string }) {
  const anim = useAnimValue(value);
  useEffect(() => {
    Animated.spring(anim, { toValue: value, friction: 7, useNativeDriver: false }).start();
  }, [value, anim]);
  const low = value < 25;
  return (
    <View style={styles.row}>
      <Text style={styles.emoji}>{emoji}</Text>
      <View style={{ flex: 1 }}>
        <View style={styles.labelRow}>
          <Text style={styles.label}>{label}</Text>
          <Text style={[styles.value, low && { color: colors.red }]}>{Math.round(value)}%</Text>
        </View>
        <View style={styles.track}>
          <Animated.View
            style={[styles.fill, { backgroundColor: color, width: anim.interpolate({ inputRange: [0, 100], outputRange: ['0%', '100%'], extrapolate: 'clamp' }) }]}
          />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', marginVertical: 6 },
  emoji: { fontSize: 22, width: 34 },
  labelRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  label: { fontSize: 13, fontWeight: '700', color: colors.text },
  value: { fontSize: 13, fontWeight: '700', color: colors.muted },
  track: { height: 12, borderRadius: radius.pill, backgroundColor: colors.bgDeep, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: radius.pill },
});
