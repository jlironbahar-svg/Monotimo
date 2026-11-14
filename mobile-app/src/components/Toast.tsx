import { useEffect } from 'react';
import { Animated, StyleSheet, Text } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useApp } from '../state/AppContext';
import { colors, radius, shadow } from '../theme';
import { useAnimValue } from '../lib/anim';

export function Toast() {
  const { toast } = useApp();
  const insets = useSafeAreaInsets();
  const anim = useAnimValue(0);
  useEffect(() => {
    if (!toast) return;
    anim.setValue(0);
    Animated.sequence([
      Animated.spring(anim, { toValue: 1, useNativeDriver: true, friction: 7 }),
      Animated.delay(Math.min(6000, 2200 + toast.text.length * 35)),
      Animated.timing(anim, { toValue: 0, duration: 250, useNativeDriver: true }),
    ]).start();
  }, [toast, anim]);

  if (!toast) return null;
  const bg = toast.tone === 'error' ? colors.red : toast.tone === 'success' ? colors.green : colors.text;
  return (
    <Animated.View
      pointerEvents="none"
      style={[
        styles.toast,
        { top: insets.top + 8, backgroundColor: bg, opacity: anim, transform: [{ translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [-30, 0] }) }] },
      ]}
    >
      <Text style={styles.text}>{toast.text}</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  toast: { position: 'absolute', left: 16, right: 16, borderRadius: radius.md, paddingVertical: 12, paddingHorizontal: 16, zIndex: 100, ...shadow },
  text: { color: '#fff', fontWeight: '700', fontSize: 14, textAlign: 'center' },
});
