import { useEffect, useRef, useState } from 'react';
import { Animated, Easing, StyleSheet, View } from 'react-native';

interface Particle {
  id: number;
  emoji: string;
  x: number;
  drift: number;
  anim: Animated.Value;
}

/** Hearts, bones and stars that float up from the avatar whenever `burst.key` changes. */
export function FloatingEmojis({ burst, count = 6, height = 200 }: { burst: { emoji: string; key: number } | null; count?: number; height?: number }) {
  const [particles, setParticles] = useState<Particle[]>([]);
  const nextId = useRef(0);

  useEffect(() => {
    if (!burst) return;
    const fresh: Particle[] = Array.from({ length: count }, (_, i) => ({
      id: nextId.current++,
      emoji: i % 3 === 2 && burst.emoji !== '💖' ? '💖' : burst.emoji,
      x: (Math.random() - 0.5) * 140,
      drift: (Math.random() - 0.5) * 60,
      anim: new Animated.Value(0),
    }));
    setParticles((p) => [...p, ...fresh]);
    fresh.forEach((p, i) => {
      Animated.timing(p.anim, {
        toValue: 1,
        duration: 1100 + Math.random() * 500,
        delay: i * 70,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }).start(() => setParticles((all) => all.filter((q) => q.id !== p.id)));
    });
  }, [burst, count]);

  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      {particles.map((p) => (
        <Animated.Text
          key={p.id}
          style={[
            styles.p,
            {
              opacity: p.anim.interpolate({ inputRange: [0, 0.15, 0.8, 1], outputRange: [0, 1, 1, 0] }),
              transform: [
                { translateX: p.anim.interpolate({ inputRange: [0, 1], outputRange: [p.x, p.x + p.drift] }) },
                { translateY: p.anim.interpolate({ inputRange: [0, 1], outputRange: [0, -height * 0.6] }) },
                { scale: p.anim.interpolate({ inputRange: [0, 0.3, 1], outputRange: [0.4, 1.15, 0.9] }) },
              ],
            },
          ]}
        >
          {p.emoji}
        </Animated.Text>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  p: { position: 'absolute', left: '50%', top: '45%', fontSize: 26, marginLeft: -13 },
});
