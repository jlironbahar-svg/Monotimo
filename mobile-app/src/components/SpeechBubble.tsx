import { useEffect } from 'react';
import { Animated, StyleSheet, Text, View } from 'react-native';

import { colors, radius, shadow } from '../theme';
import { useAnimValue } from '../lib/anim';

/** Rounded bubble with a little tail; pops in whenever the text changes. */
export function SpeechBubble({ text, tone = 'friend', maxLines }: { text: string; tone?: 'friend' | 'thinking'; maxLines?: number }) {
  const pop = useAnimValue(1);
  useEffect(() => {
    pop.setValue(0.85);
    Animated.spring(pop, { toValue: 1, friction: 5, tension: 160, useNativeDriver: true }).start();
  }, [text, pop]);
  if (!text) return null;
  return (
    <Animated.View style={[styles.wrap, { transform: [{ scale: pop }] }]}>
      <View style={[styles.bubble, tone === 'thinking' && styles.thinking]}>
        <Text style={[styles.text, tone === 'thinking' && styles.thinkingText]} numberOfLines={maxLines}>
          {text}
        </Text>
      </View>
      <View style={[styles.tail, tone === 'thinking' && styles.thinkingTail]} />
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', marginHorizontal: 24 },
  bubble: { backgroundColor: colors.card, borderRadius: radius.lg, paddingHorizontal: 18, paddingVertical: 12, maxWidth: 340, ...shadow },
  text: { fontSize: 16, color: colors.text, textAlign: 'center', lineHeight: 22 },
  thinking: { backgroundColor: colors.primarySoft },
  thinkingText: { color: colors.primaryDark, fontStyle: 'italic' },
  tail: {
    width: 16,
    height: 16,
    backgroundColor: colors.card,
    transform: [{ rotate: '45deg' }],
    marginTop: -9,
  },
  thinkingTail: { backgroundColor: colors.primarySoft },
});
