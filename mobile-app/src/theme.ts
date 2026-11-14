import { Platform } from 'react-native';

export const colors = {
  bg: '#F3F6FF',
  bgDeep: '#E4ECFF',
  card: '#FFFFFF',
  text: '#1B2A4A',
  muted: '#6B7A99',
  faint: '#A9B4CC',
  primary: '#2F7BFF', // same blue as the PC cursor
  primaryDark: '#1F5FD6',
  primarySoft: '#E3ECFF',
  pink: '#FF7EB6',
  pinkSoft: '#FFE3F0',
  yellow: '#FFC94D',
  yellowSoft: '#FFF3D1',
  green: '#3CCF91',
  greenSoft: '#DDF7EA',
  red: '#FF6B6B',
  redSoft: '#FFE3E3',
  purple: '#9B7BFF',
  purpleSoft: '#EEE8FF',
  // puppy palette
  fur: '#F6D7B0',
  furDark: '#E9BE8C',
  furPatch: '#C98F5E',
  ear: '#B47A4C',
  muzzle: '#FFF4E6',
  nose: '#3B2A2A',
  blush: 'rgba(255,120,150,0.45)',
};

export const radius = { sm: 12, md: 18, lg: 24, xl: 32, pill: 999 };

export const shadow = Platform.select({
  android: { elevation: 4 },
  default: {
    shadowColor: '#2F4C8A',
    shadowOpacity: 0.12,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 6 },
  },
}) as object;

export const font = {
  title: { fontSize: 26, fontWeight: '800' as const, color: colors.text },
  h2: { fontSize: 18, fontWeight: '800' as const, color: colors.text },
  body: { fontSize: 15, color: colors.text },
  small: { fontSize: 13, color: colors.muted },
};
