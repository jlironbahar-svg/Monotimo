import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useApp } from '../state/AppContext';
import { colors, radius, shadow } from '../theme';
import { Icon, type IconName } from './ui';

export type Mode = 'pet' | 'control' | 'apps' | 'settings';

export const MODES: { key: Mode; icon: IconName; activeIcon: IconName; label: string; color: string; soft: string }[] = [
  { key: 'pet', icon: 'paw-outline', activeIcon: 'paw', label: 'Tamagotchi', color: colors.pink, soft: colors.pinkSoft },
  { key: 'control', icon: 'desktop-outline', activeIcon: 'desktop', label: 'PC Control', color: colors.primary, soft: colors.primarySoft },
  { key: 'apps', icon: 'rocket-outline', activeIcon: 'rocket', label: 'Apps', color: colors.yellow, soft: colors.yellowSoft },
  { key: 'settings', icon: 'settings-outline', activeIcon: 'settings', label: 'Settings', color: colors.green, soft: colors.greenSoft },
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
            <Icon name={active ? m.activeIcon : m.icon} size={21} color={active ? (m.key === 'apps' ? colors.text : '#fff') : m.key === 'apps' ? '#B8860B' : m.color} />
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
  label: { fontSize: 11.5, fontWeight: '800', marginTop: 2 },
});
