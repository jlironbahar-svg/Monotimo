import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';

import { useApp } from '../state/AppContext';
import { colors, radius, shadow } from '../theme';

export function Card({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function SectionTitle({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <View style={styles.sectionRow}>
      <Text style={styles.section}>{children}</Text>
      {right}
    </View>
  );
}

type Tone = 'primary' | 'pink' | 'yellow' | 'green' | 'soft' | 'danger';
const TONES: Record<Tone, { bg: string; fg: string }> = {
  primary: { bg: colors.primary, fg: '#fff' },
  pink: { bg: colors.pink, fg: '#fff' },
  yellow: { bg: colors.yellow, fg: colors.text },
  green: { bg: colors.green, fg: '#fff' },
  soft: { bg: colors.primarySoft, fg: colors.text },
  danger: { bg: colors.redSoft, fg: '#C0392B' },
};

export function PillButton({
  label,
  emoji,
  onPress,
  tone = 'primary',
  disabled,
  busy,
  style,
  small,
}: {
  label: string;
  emoji?: string;
  onPress: () => void;
  tone?: Tone;
  disabled?: boolean;
  busy?: boolean;
  style?: StyleProp<ViewStyle>;
  small?: boolean;
}) {
  const { tap, sfx } = useApp();
  const t = TONES[tone];
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled || busy}
      onPress={() => {
        tap();
        sfx('pop');
        onPress();
      }}
      style={({ pressed }) => [
        styles.pill,
        small && styles.pillSmall,
        { backgroundColor: t.bg, opacity: disabled ? 0.45 : 1, transform: [{ scale: pressed ? 0.96 : 1 }] },
        style,
      ]}
    >
      {busy ? (
        <ActivityIndicator color={t.fg} />
      ) : (
        <Text style={[styles.pillText, small && styles.pillTextSmall, { color: t.fg }]}>
          {emoji ? `${emoji}  ` : ''}
          {label}
        </Text>
      )}
    </Pressable>
  );
}

/** Square tile with a big emoji, used for quick actions and app shortcuts. */
export function Tile({
  emoji,
  label,
  onPress,
  onLongPress,
  color = colors.primarySoft,
  disabled,
}: {
  emoji: string;
  label: string;
  onPress: () => void;
  onLongPress?: () => void;
  color?: string;
  disabled?: boolean;
}) {
  const { tap, sfx } = useApp();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      disabled={disabled}
      onLongPress={onLongPress}
      onPress={() => {
        tap();
        sfx('pop');
        onPress();
      }}
      style={({ pressed }) => [styles.tile, { backgroundColor: color, opacity: disabled ? 0.45 : 1, transform: [{ scale: pressed ? 0.94 : 1 }] }]}
    >
      <Text style={styles.tileEmoji}>{emoji}</Text>
      <Text style={styles.tileLabel} numberOfLines={2}>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.card, borderRadius: radius.lg, padding: 16, ...shadow },
  sectionRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 18, marginBottom: 8, paddingHorizontal: 4 },
  section: { fontSize: 13, fontWeight: '800', color: colors.muted, letterSpacing: 0.8, textTransform: 'uppercase' },
  pill: { borderRadius: radius.pill, paddingVertical: 13, paddingHorizontal: 20, alignItems: 'center', justifyContent: 'center' },
  pillSmall: { paddingVertical: 8, paddingHorizontal: 14 },
  pillText: { fontSize: 16, fontWeight: '800' },
  pillTextSmall: { fontSize: 14 },
  tile: { width: '31%', aspectRatio: 1, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', padding: 6, marginBottom: 10 },
  tileEmoji: { fontSize: 30 },
  tileLabel: { marginTop: 6, fontSize: 12.5, fontWeight: '700', color: colors.text, textAlign: 'center' },
});
