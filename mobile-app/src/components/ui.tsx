import Ionicons from '@expo/vector-icons/Ionicons';
import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';

import { useApp } from '../state/AppContext';
import { colors, radius, shadow } from '../theme';

export type IconName = React.ComponentProps<typeof Ionicons>['name'];

export function Icon({ name, size = 20, color = colors.text }: { name: IconName; size?: number; color?: string }) {
  return <Ionicons name={name} size={size} color={color} />;
}

export function Card({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function SectionTitle({ children, right, icon }: { children: React.ReactNode; right?: React.ReactNode; icon?: IconName }) {
  return (
    <View style={styles.sectionRow}>
      <View style={styles.sectionLeft}>
        {icon ? <Ionicons name={icon} size={14} color={colors.muted} style={{ marginRight: 6 }} /> : null}
        <Text style={styles.section}>{children}</Text>
      </View>
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
  icon,
  onPress,
  tone = 'primary',
  disabled,
  busy,
  style,
  small,
}: {
  label: string;
  emoji?: string;
  icon?: IconName;
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
      accessibilityLabel={label}
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
        <View style={styles.pillInner}>
          {icon ? <Ionicons name={icon} size={small ? 16 : 19} color={t.fg} style={{ marginRight: 8 }} /> : null}
          <Text style={[styles.pillText, small && styles.pillTextSmall, { color: t.fg }]}>
            {emoji ? `${emoji}  ` : ''}
            {label}
          </Text>
        </View>
      )}
    </Pressable>
  );
}

/** Square tile: a coloured icon badge (or a big emoji) and a label. Used for quick actions and launchers. */
export function Tile({
  emoji,
  icon,
  tint = colors.primary,
  label,
  sublabel,
  onPress,
  onLongPress,
  color = colors.card,
  disabled,
}: {
  emoji?: string;
  icon?: IconName;
  tint?: string;
  label: string;
  sublabel?: string;
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
      {icon ? (
        <View style={[styles.badge, { backgroundColor: tint + '1F' }]}>
          <Ionicons name={icon} size={24} color={tint} />
        </View>
      ) : (
        <Text style={styles.tileEmoji}>{emoji}</Text>
      )}
      <Text style={styles.tileLabel} numberOfLines={2}>
        {label}
      </Text>
      {sublabel ? (
        <Text style={styles.tileSub} numberOfLines={1}>
          {sublabel}
        </Text>
      ) : null}
    </Pressable>
  );
}

/** Small rounded chip button, used for the shortcut rows. */
export function Chip({ label, icon, onPress, disabled, tint = colors.primary }: { label: string; icon: IconName; onPress: () => void; disabled?: boolean; tint?: string }) {
  const { tap, sfx } = useApp();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      disabled={disabled}
      onPress={() => {
        tap();
        sfx('pop');
        onPress();
      }}
      style={({ pressed }) => [styles.chip, { opacity: disabled ? 0.45 : 1, transform: [{ scale: pressed ? 0.95 : 1 }] }]}
    >
      <Ionicons name={icon} size={16} color={tint} />
      <Text style={styles.chipText}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.card, borderRadius: radius.lg, padding: 16, ...shadow },
  sectionRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 20, marginBottom: 10, paddingHorizontal: 4 },
  sectionLeft: { flexDirection: 'row', alignItems: 'center' },
  section: { fontSize: 12.5, fontWeight: '800', color: colors.muted, letterSpacing: 0.9, textTransform: 'uppercase' },
  pill: { borderRadius: radius.pill, paddingVertical: 13, paddingHorizontal: 20, alignItems: 'center', justifyContent: 'center' },
  pillSmall: { paddingVertical: 8, paddingHorizontal: 14 },
  pillInner: { flexDirection: 'row', alignItems: 'center' },
  pillText: { fontSize: 16, fontWeight: '800' },
  pillTextSmall: { fontSize: 14 },
  tile: { width: '31.5%', aspectRatio: 1, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', padding: 8, marginBottom: 10, ...shadow },
  badge: { width: 46, height: 46, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  tileEmoji: { fontSize: 30 },
  tileLabel: { marginTop: 8, fontSize: 12.5, fontWeight: '700', color: colors.text, textAlign: 'center' },
  tileSub: { fontSize: 10.5, color: colors.muted, marginTop: 1 },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.card,
    borderRadius: radius.pill,
    paddingHorizontal: 12,
    paddingVertical: 9,
    marginRight: 8,
    marginBottom: 8,
    ...shadow,
  },
  chipText: { fontSize: 13, fontWeight: '700', color: colors.text },
});
