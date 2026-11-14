import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useApp } from '../state/AppContext';
import { colors, radius, shadow } from '../theme';

export type Mode = 'pet' | 'control' | 'apps' | 'settings';

export const MODES: { key: Mode; emoji: string; label: string; color: string; soft: string }[] = [
  { key: 'pet', emoji: '🐶', label: 'Tamagotchi', color: colors.pink, soft: colors.pinkSoft },
  { key: 'control', emoji: '🖱️', label: 'PC Control', color: colors.primary, soft: colors.primarySoft },
  { key: 'apps', emoji: '🚀', label: 'Apps', color: colors.yellow, soft: colors.yellowSoft },
  { key: 'settings', emoji: '⚙️', label: 'Settings', color: colors.green, soft: colors.greenSoft },
];

/** Four clearly separated pill buttons, one per mode. */
export function ModeBar({ mode, onChange }: { mode: Mode; onChange: (m: Mode) => void }) {
  const insets = useSafeAreaInsets();
  const { tap, sfx } = useApp();
  return (
    <View style={[styles.bar, { paddingBottom: Math.max(insets.bottom, 10) }]}>
      {MODES.map((m) => {
        const active = m.key === mode;
        return (
          <Pressable
            key={m.key}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            accessibilityLabel={m.label}
            onPress={() => {
              if (!active) {
                tap();
                sfx('boop');
                onChange(m.key);
              }
            }}
            style={({ pressed }) => [
              styles.pill,
              { backgroundColor: active ? m.color : m.soft, transform: [{ scale: pressed ? 0.95 : active ? 1.04 : 1 }] },
              active && shadow,
            ]}
          >
            <Text style={styles.emoji}>{m.emoji}</Text>
            <Text style={[styles.label, { color: active ? (m.key === 'apps' ? colors.text : '#fff') : colors.text }]} numberOfLines={1}>
              {m.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: { flexDirection: 'row', justifyContent: 'space-between', gap: 8, paddingHorizontal: 12, paddingTop: 10, backgroundColor: colors.bg },
  pill: { flex: 1, borderRadius: radius.pill, paddingVertical: 9, alignItems: 'center' },
  emoji: { fontSize: 20 },
  label: { fontSize: 11.5, fontWeight: '800', marginTop: 2 },
});
