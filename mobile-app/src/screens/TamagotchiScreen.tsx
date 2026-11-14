import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { Avatar } from '../components/Avatar';
import { FloatingEmojis } from '../components/FloatingEmojis';
import { SpeechBubble } from '../components/SpeechBubble';
import { StatBar } from '../components/StatBar';
import { StatusPill } from '../components/StatusPill';
import { Card, PillButton } from '../components/ui';
import { idleLine, level, levelProgress, petMood, type PetAction } from '../lib/pet';
import { useApp } from '../state/AppContext';
import { colors, font, radius } from '../theme';

const ACTIONS: { key: PetAction; emoji: string; label: string; tone: 'pink' | 'yellow' | 'green' | 'primary' }[] = [
  { key: 'feed', emoji: '🦴', label: 'Feed', tone: 'yellow' },
  { key: 'pet', emoji: '✋', label: 'Pet', tone: 'pink' },
  { key: 'play', emoji: '🎾', label: 'Play', tone: 'green' },
  { key: 'nap', emoji: '💤', label: 'Nap', tone: 'primary' },
];

/** Virtual pet: feed, pet and play with your desktop friend. */
export function TamagotchiScreen() {
  const { pet, petAction, settings, reactionMood, talking, burst, messages } = useApp();
  const name = settings.petName || 'Biscuit';
  const [local, setLocal] = useState(() => ({ text: idleLine(pet, name), at: Date.now() }));
  const setLine = (text: string) => setLocal({ text, at: Date.now() });
  const mood = reactionMood ?? petMood(pet);

  // occasionally say something new
  useEffect(() => {
    const t = setInterval(() => setLocal({ text: idleLine(pet, name), at: Date.now() }), 14000);
    return () => clearInterval(t);
  }, [pet, name]);

  // when the PC replies, show it here too
  const lastFriend = [...messages].reverse().find((m) => m.from === 'friend');
  const line = lastFriend && lastFriend.ts > local.at ? lastFriend.text : local.text;

  const act = (a: PetAction) => setLine(petAction(a).message);
  const lvl = level(pet.xp);

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <View>
          <Text style={styles.greeting}>{greeting()}</Text>
          <Text style={styles.name}>{name}</Text>
          <View style={styles.levelRow}>
            <Text style={styles.level}>Lv {lvl}</Text>
            <View style={styles.xpTrack}>
              <View style={[styles.xpFill, { width: `${Math.round(levelProgress(pet.xp) * 100)}%` }]} />
            </View>
          </View>
        </View>
        <StatusPill />
      </View>

      <SpeechBubble text={line} />
      <View style={styles.stage}>
        <Avatar uri={settings.avatarUri} size={230} mood={mood} talking={talking} onPress={() => act('pet')} />
        <FloatingEmojis burst={burst} height={260} />
      </View>

      <View style={styles.actions}>
        {ACTIONS.map((a) => (
          <PillButton key={a.key} label={a.label} emoji={a.emoji} tone={a.tone} onPress={() => act(a.key)} style={styles.action} />
        ))}
      </View>

      <Card style={{ marginTop: 14 }}>
        <StatBar emoji="❤️" label="Happiness" value={pet.happiness} color={colors.pink} />
        <StatBar emoji="⚡" label="Energy" value={pet.energy} color={colors.yellow} />
        <StatBar emoji="🍖" label="Tummy" value={pet.fullness} color={colors.green} />
      </Card>
      <Text style={styles.tip}>{`Tip: tap ${name} for pets. Stats slowly drop while you're away, so come back and say hi!`}</Text>
    </ScrollView>
  );
}

function greeting(): string {
  const h = new Date().getHours();
  if (h < 5) return 'Up late? 🌙';
  if (h < 12) return 'Good morning ☀️';
  if (h < 18) return 'Good afternoon';
  return 'Good evening ✨';
}

const styles = StyleSheet.create({
  greeting: { fontSize: 13, fontWeight: '700', color: colors.muted },
  content: { padding: 16, paddingBottom: 24 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  name: { ...font.title },
  levelRow: { flexDirection: 'row', alignItems: 'center', marginTop: 2 },
  level: { fontWeight: '800', color: colors.purple, marginRight: 8 },
  xpTrack: { width: 90, height: 8, borderRadius: radius.pill, backgroundColor: colors.purpleSoft, overflow: 'hidden' },
  xpFill: { height: '100%', backgroundColor: colors.purple, borderRadius: radius.pill },
  stage: { alignItems: 'center', justifyContent: 'center', height: 270, marginTop: 4 },
  actions: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', gap: 10, marginTop: 4 },
  action: { width: '48%' },
  tip: { ...font.small, textAlign: 'center', marginTop: 14, paddingHorizontal: 12 },
});
