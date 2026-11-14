import React, { useEffect, useMemo } from 'react';
import { Animated, Easing, Pressable, StyleSheet, Text, View, type ViewStyle } from 'react-native';

import type { Mood } from '../../../shared/protocol';
import { colors } from '../theme';
import { useAnimValue } from '../lib/anim';

interface Props {
  size?: number;
  mood?: Mood;
  talking?: boolean;
  onPress?: () => void;
}

/**
 * The default companion: a chibi puppy drawn with plain Views so every part (eyes, ears,
 * tail, mouth) can be animated on the native driver.
 */
export function Puppy({ size = 220, mood = 'happy', talking = false, onPress }: Props) {
  const S = size;
  const box = (x: number, y: number, w: number, h: number, r?: number): ViewStyle => ({
    position: 'absolute',
    left: x * S,
    top: y * S,
    width: w * S,
    height: h * S,
    borderRadius: r === undefined ? Math.min(w, h) * S * 0.5 : r * S,
  });

  const bounce = useAnimValue(0);
  const blink = useAnimValue(0);
  const tail = useAnimValue(0);
  const ear = useAnimValue(0);
  const mouth = useAnimValue(0);
  const squish = useAnimValue(0);
  const zzz = useAnimValue(0);

  const excited = mood === 'excited' || mood === 'proud';
  const sleepy = mood === 'sleepy';
  const sad = mood === 'sad';

  // idle bounce / breathing (faster hops when excited, slow breathing when sleepy)
  useEffect(() => {
    const half = excited ? 260 : sleepy ? 1600 : 900;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(bounce, { toValue: 1, duration: half, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(bounce, { toValue: 0, duration: half, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [bounce, excited, sleepy]);

  // tail wag speed follows the mood
  useEffect(() => {
    const d = excited ? 110 : sleepy ? 1200 : sad ? 700 : 260;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(tail, { toValue: 1, duration: d, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
        Animated.timing(tail, { toValue: -1, duration: d, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [tail, excited, sleepy, sad]);

  // random blinks and ear wiggles
  useEffect(() => {
    let alive = true;
    let t: ReturnType<typeof setTimeout>;
    const schedule = () => {
      t = setTimeout(() => {
        if (!alive) return;
        Animated.sequence([
          Animated.timing(blink, { toValue: 1, duration: 70, useNativeDriver: true }),
          Animated.timing(blink, { toValue: 0, duration: 90, useNativeDriver: true }),
        ]).start();
        if (Math.random() < 0.45) {
          Animated.sequence([
            Animated.timing(ear, { toValue: 1, duration: 90, useNativeDriver: true }),
            Animated.timing(ear, { toValue: -0.6, duration: 110, useNativeDriver: true }),
            Animated.spring(ear, { toValue: 0, friction: 3, useNativeDriver: true }),
          ]).start();
        }
        schedule();
      }, 2200 + Math.random() * 2800);
    };
    schedule();
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [blink, ear]);

  // mouth flaps while the voice plays
  useEffect(() => {
    if (!talking) {
      Animated.timing(mouth, { toValue: 0, duration: 120, useNativeDriver: true }).start();
      return;
    }
    const iv = setInterval(() => {
      Animated.timing(mouth, { toValue: 0.25 + Math.random() * 0.75, duration: 90, useNativeDriver: true }).start();
    }, 120);
    return () => clearInterval(iv);
  }, [talking, mouth]);

  // floating Zzz while sleepy
  useEffect(() => {
    if (!sleepy) return;
    const loop = Animated.loop(Animated.timing(zzz, { toValue: 1, duration: 2200, easing: Easing.out(Easing.quad), useNativeDriver: true }));
    zzz.setValue(0);
    loop.start();
    return () => loop.stop();
  }, [sleepy, zzz]);

  const press = () => {
    squish.setValue(1);
    Animated.spring(squish, { toValue: 0, friction: 3, tension: 160, useNativeDriver: true }).start();
    onPress?.();
  };

  const hop = excited ? 0.06 : 0.025;
  const groupStyle = {
    transform: [
      { translateY: bounce.interpolate({ inputRange: [0, 1], outputRange: [0, -hop * S] }) },
      { rotate: mood === 'curious' ? '-7deg' : '0deg' },
      { scaleX: squish.interpolate({ inputRange: [0, 1], outputRange: [1, 1.1] }) },
      { scaleY: Animated.add(bounce.interpolate({ inputRange: [0, 1], outputRange: [1, 1.015] }), squish.interpolate({ inputRange: [0, 1], outputRange: [0, -0.12] })) },
    ],
  };
  const shadowStyle = {
    transform: [{ scaleX: bounce.interpolate({ inputRange: [0, 1], outputRange: [1, excited ? 0.75 : 0.9] }) }],
    opacity: bounce.interpolate({ inputRange: [0, 1], outputRange: [1, 0.7] }),
  };
  const eyeStyle = { transform: [{ scaleY: blink.interpolate({ inputRange: [0, 1], outputRange: [1, 0.08] }) }] };
  const earRot = (base: number) => ({
    transform: [{ rotate: ear.interpolate({ inputRange: [-1, 1], outputRange: [`${base - 14}deg`, `${base + 14}deg`] }) }],
  });
  const tailStyle = { transform: [{ rotate: tail.interpolate({ inputRange: [-1, 1], outputRange: ['10deg', '50deg'] }) }] };
  const mouthStyle = { transform: [{ scaleY: mouth.interpolate({ inputRange: [0, 1], outputRange: [0.15, 1] }) }] };

  const eyes = useMemo(() => {
    if (sleepy || excited) {
      // closed ︶ (sleepy) or happy ^ ^ (excited)
      const arc = (x: number): ViewStyle => ({
        ...box(x, sleepy ? 0.3 : 0.29, 0.1, 0.06, 0.05),
        borderColor: colors.nose,
        ...(sleepy ? { borderBottomWidth: 0.016 * S } : { borderTopWidth: 0.018 * S }),
      });
      return (
        <>
          <View style={arc(0.325)} />
          <View style={arc(0.575)} />
        </>
      );
    }
    const big = mood === 'curious' ? 0.115 : 0.1;
    const eye = (cx: number, d: number) => (
      <Animated.View style={[box(cx - d / 2, 0.32 - d / 2, d, d), { backgroundColor: colors.nose }, eyeStyle]}>
        <View style={[box(d * 0.52, d * 0.14, d * 0.34, d * 0.34), { backgroundColor: '#fff' }]} />
        <View style={[box(d * 0.25, d * 0.6, d * 0.16, d * 0.16), { backgroundColor: 'rgba(255,255,255,0.75)' }]} />
      </Animated.View>
    );
    return (
      <>
        {eye(0.375, 0.1)}
        {eye(0.625, big)}
      </>
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [S, sleepy, excited, mood]);

  let mouthEl: React.ReactNode;
  if (talking) {
    mouthEl = (
      <Animated.View style={[box(0.445, 0.465, 0.11, 0.1), { borderTopLeftRadius: 0.02 * S, borderTopRightRadius: 0.02 * S, backgroundColor: '#8A3A3A', overflow: 'hidden', transformOrigin: '50% 0%' }, mouthStyle]}>
        <View style={[box(0.02, 0.055, 0.07, 0.06, 0.035), { backgroundColor: '#FF8FA3' }]} />
      </Animated.View>
    );
  } else if (excited) {
    mouthEl = (
      <View style={[box(0.445, 0.465, 0.11, 0.085), { borderTopLeftRadius: 0.015 * S, borderTopRightRadius: 0.015 * S, backgroundColor: '#8A3A3A', overflow: 'hidden' }]}>
        <View style={[box(0.02, 0.04, 0.07, 0.06, 0.035), { backgroundColor: '#FF8FA3' }]} />
      </View>
    );
  } else if (sad) {
    mouthEl = <View style={[box(0.46, 0.48, 0.08, 0.04, 0.04), { borderTopWidth: 0.012 * S, borderColor: colors.nose }]} />;
  } else {
    const w = (x: number) => <View style={[box(x, 0.44, 0.065, 0.045, 0.0325), { borderBottomWidth: 0.012 * S, borderColor: colors.nose }]} />;
    mouthEl = (
      <>
        {w(0.4375)}
        {w(0.4975)}
      </>
    );
  }

  return (
    <Pressable onPress={press} hitSlop={10} accessibilityRole="button" accessibilityLabel="Your puppy friend">
      <View style={{ width: S, height: S }}>
        <Animated.View style={[box(0.25, 0.9, 0.5, 0.06), { backgroundColor: 'rgba(27,42,74,0.12)' }, shadowStyle]} />
        <Animated.View style={[StyleSheet.absoluteFill, groupStyle]}>
          {/* tail, body, paws */}
          <Animated.View style={[box(0.665, 0.6, 0.075, 0.2, 0.0375), { backgroundColor: colors.ear, transformOrigin: '50% 100%' }, tailStyle]} />
          <View style={[box(0.27, 0.58, 0.46, 0.3, 0.15), { backgroundColor: colors.furDark }]} />
          <View style={[box(0.36, 0.66, 0.28, 0.19, 0.1), { backgroundColor: colors.muzzle }]} />
          <View style={[box(0.29, 0.82, 0.16, 0.09), { backgroundColor: colors.muzzle, borderWidth: 0.008 * S, borderColor: colors.furDark }]} />
          <View style={[box(0.55, 0.82, 0.16, 0.09), { backgroundColor: colors.muzzle, borderWidth: 0.008 * S, borderColor: colors.furDark }]} />
          {/* collar + tag */}
          <View style={[box(0.31, 0.61, 0.38, 0.055, 0.0275), { backgroundColor: colors.primary }]} />
          <View style={[box(0.475, 0.64, 0.05, 0.05), { backgroundColor: colors.yellow, borderWidth: 0.006 * S, borderColor: '#E0A800' }]} />
          {/* head */}
          <View
            style={[
              box(0.15, 0.06, 0.7, 0.58),
              {
                backgroundColor: colors.fur,
                borderTopLeftRadius: 0.33 * S,
                borderTopRightRadius: 0.33 * S,
                borderBottomLeftRadius: 0.27 * S,
                borderBottomRightRadius: 0.27 * S,
              },
            ]}
          />
          <View style={[box(0.55, 0.215, 0.2, 0.2), { backgroundColor: colors.furPatch, opacity: 0.85 }]} />
          <View style={[box(0.335, 0.38, 0.33, 0.21, 0.105), { backgroundColor: colors.muzzle }]} />
          <View style={[box(0.225, 0.43, 0.1, 0.055), { backgroundColor: colors.blush }]} />
          <View style={[box(0.675, 0.43, 0.1, 0.055), { backgroundColor: colors.blush }]} />
          {eyes}
          {sad && (
            <>
              <View style={[box(0.32, 0.235, 0.11, 0.02, 0.01), { backgroundColor: colors.ear, transform: [{ rotate: '-14deg' }] }]} />
              <View style={[box(0.57, 0.235, 0.11, 0.02, 0.01), { backgroundColor: colors.ear, transform: [{ rotate: '14deg' }] }]} />
              <View style={[box(0.335, 0.375, 0.03, 0.045, 0.015), { backgroundColor: '#7CC4FF' }]} />
            </>
          )}
          {/* nose */}
          <View style={[box(0.45, 0.39, 0.1, 0.068), { backgroundColor: colors.nose, borderBottomLeftRadius: 0.05 * S, borderBottomRightRadius: 0.05 * S, borderTopLeftRadius: 0.03 * S, borderTopRightRadius: 0.03 * S }]}>
            <View style={[box(0.02, 0.012, 0.03, 0.018), { backgroundColor: 'rgba(255,255,255,0.55)' }]} />
          </View>
          {mouthEl}
          {/* floppy ears, drawn over the head edges */}
          <Animated.View style={[box(0.075, 0.1, 0.21, 0.37, 0.105), { backgroundColor: colors.ear, transformOrigin: '50% 8%' }, earRot(16)]} />
          <Animated.View style={[box(0.715, 0.1, 0.21, 0.37, 0.105), { backgroundColor: colors.ear, transformOrigin: '50% 8%' }, earRot(-16)]} />
          {sleepy && (
            <Animated.Text
              style={[
                styles.zzz,
                { left: 0.74 * S, top: 0.02 * S, fontSize: 0.1 * S },
                {
                  opacity: zzz.interpolate({ inputRange: [0, 0.2, 1], outputRange: [0, 1, 0] }),
                  transform: [
                    { translateY: zzz.interpolate({ inputRange: [0, 1], outputRange: [0, -0.12 * S] }) },
                    { translateX: zzz.interpolate({ inputRange: [0, 1], outputRange: [0, 0.06 * S] }) },
                  ],
                },
              ]}
            >
              z<Text style={{ fontSize: 0.075 * S }}>z</Text>
            </Animated.Text>
          )}
        </Animated.View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  zzz: { position: 'absolute', fontWeight: '800', color: colors.purple },
});
