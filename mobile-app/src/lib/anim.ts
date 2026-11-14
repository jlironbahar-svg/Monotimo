import { useState } from 'react';
import { Animated } from 'react-native';

/** A stable Animated.Value for the component's lifetime (a lint-friendly replacement for a ref holding one). */
export function useAnimValue(initial = 0): Animated.Value {
  const [value] = useState(() => new Animated.Value(initial));
  return value;
}
