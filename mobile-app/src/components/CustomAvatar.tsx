import { LinearGradient } from 'expo-linear-gradient';
import { useEffect } from 'react';
import { Animated, Easing, Image, Pressable, StyleSheet, View } from 'react-native';

import type { Mood } from '../../../shared/protocol';
import { colors } from '../theme';
import { useAnimValue } from '../lib/anim';

interface Props {
  uri: string;
  size?: number;
  mood?: Mood;
  talking?: boolean;
  onPress?: () => void;
}

/** Any photo from the gallery, brought to life with float, wobble, "blink" squash, bounce and talk pulses. */
export function CustomAvatar({ uri, size = 220, mood = 'happy', talking = false, onPress }: Props) {
  const float = useAnimValue(0);
  const wobble = useAnimValue(0);
  const blink = useAnimValue(0);
  const bounce = useAnimValue(0);
  const talk = useAnimValue(0);
  const sparkle = useAnimValue(0);

  const excited = mood === 'excited' || mood === 'proud';
  const sleepy = mood === 'sleepy';

  useEffect(() => {
    const d = excited ? 420 : sleepy ? 2000 : 1300;
    const loop = Animated.loop(
      Animated.parallel([
        Animated.sequence([
          Animated.timing(float, { toValue: 1, duration: d, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
          Animated.timing(float, { toValue: 0, duration: d, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        ]),
        Animated.sequence([
          Animated.timing(wobble, { toValue: 1, duration: d * 1.3, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
          Animated.timing(wobble, { toValue: -1, duration: d * 1.3, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        ]),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [float, wobble, excited, sleepy]);

  // "blink": a quick squash every few seconds, with a sparkle
  useEffect(() => {
    let alive = true;
    let t: ReturnType<typeof setTimeout>;
    const next = () => {
      t = setTimeout(() => {
        if (!alive) return;
        Animated.sequence([
          Animated.timing(blink, { toValue: 1, duration: 80, useNativeDriver: true }),
          Animated.timing(blink, { toValue: 0, duration: 120, useNativeDriver: true }),
        ]).start();
        sparkle.setValue(0);
        Animated.timing(sparkle, { toValue: 1, duration: 900, useNativeDriver: true }).start();
        next();
      }, 2600 + Math.random() * 2600);
    };
    next();
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [blink, sparkle]);

  useEffect(() => {
    if (!talking) {
      Animated.spring(talk, { toValue: 0, useNativeDriver: true }).start();
      return;
    }
    const iv = setInterval(() => {
      Animated.timing(talk, { toValue: 0.3 + Math.random() * 0.7, duration: 100, useNativeDriver: true }).start();
    }, 130);
    return () => clearInterval(iv);
  }, [talking, talk]);

  const press = () => {
    bounce.setValue(1);
    Animated.spring(bounce, { toValue: 0, friction: 3, tension: 150, useNativeDriver: true }).start();
    onPress?.();
  };

  const ring = size;
  const img = size - 16;
  const style = {
    transform: [
      { translateY: float.interpolate({ inputRange: [0, 1], outputRange: [0, excited ? -16 : -8] }) },
      { rotate: wobble.interpolate({ inputRange: [-1, 1], outputRange: sleepy ? ['-2deg', '2deg'] : ['-5deg', '5deg'] }) },
      { scale: Animated.add(1, Animated.add(Animated.multiply(talk, 0.05), Animated.multiply(bounce, 0.1))) },
      { scaleY: blink.interpolate({ inputRange: [0, 1], outputRange: [1, 0.9] }) },
    ],
  };

  return (
    <Pressable onPress={press} accessibilityRole="button" accessibilityLabel="Your custom friend">
      <View style={{ width: size, height: size + 20, alignItems: 'center' }}>
        <Animated.View style={style}>
          <LinearGradient colors={[colors.pink, colors.primary, colors.yellow]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[styles.ring, { width: ring, height: ring, borderRadius: ring / 2 }]}>
            <Image source={{ uri }} style={{ width: img, height: img, borderRadius: img / 2, opacity: sleepy ? 0.8 : 1 }} />
          </LinearGradient>
          <Animated.Text
            style={[
              styles.sparkle,
              {
                opacity: sparkle.interpolate({ inputRange: [0, 0.2, 1], outputRange: [0, 1, 0] }),
                transform: [{ scale: sparkle.interpolate({ inputRange: [0, 1], outputRange: [0.6, 1.3] }) }],
              },
            ]}
          >
            ✨
          </Animated.Text>
          {sleepy && <Animated.Text style={styles.zzz}>💤</Animated.Text>}
        </Animated.View>
        <Animated.View
          style={[
            styles.shadow,
            { width: size * 0.55, transform: [{ scaleX: float.interpolate({ inputRange: [0, 1], outputRange: [1, 0.8] }) }] },
          ]}
        />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  ring: { alignItems: 'center', justifyContent: 'center' },
  sparkle: { position: 'absolute', right: 6, top: 4, fontSize: 28 },
  zzz: { position: 'absolute', right: -6, top: -10, fontSize: 30 },
  shadow: { height: 12, borderRadius: 6, backgroundColor: 'rgba(27,42,74,0.12)', marginTop: 6 },
});
