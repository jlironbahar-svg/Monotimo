import { useState } from 'react';
import { Alert, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { StatusPill } from '../components/StatusPill';
import { Card, PillButton, SectionTitle, Tile } from '../components/ui';
import { useApp, type Shortcut } from '../state/AppContext';
import { colors, font, radius } from '../theme';

const APPS = [
  { emoji: '🌐', label: 'Browser', name: 'browser' },
  { emoji: '📝', label: 'Notepad', name: 'notepad' },
  { emoji: '🧮', label: 'Calculator', name: 'calculator' },
  { emoji: '📁', label: 'Files', name: 'file explorer' },
  { emoji: '💻', label: 'Terminal', name: 'terminal' },
  { emoji: '⚙️', label: 'Settings', name: 'settings' },
  { emoji: '🎵', label: 'Spotify', name: 'spotify' },
  { emoji: '🧑‍💻', label: 'VS Code', name: 'vs code' },
  { emoji: '📊', label: 'Task Manager', name: 'task manager' },
];

const SITES = [
  { emoji: '▶️', label: 'YouTube', url: 'https://www.youtube.com' },
  { emoji: '✉️', label: 'Gmail', url: 'https://mail.google.com' },
  { emoji: '🗺️', label: 'Maps', url: 'https://maps.google.com' },
  { emoji: '🐙', label: 'GitHub', url: 'https://github.com' },
  { emoji: '🎬', label: 'Netflix', url: 'https://www.netflix.com' },
  { emoji: '📚', label: 'Wikipedia', url: 'https://www.wikipedia.org' },
];

const KEYS: { emoji: string; label: string; keys: string[] }[] = [
  { emoji: '⏯️', label: 'Play / pause', keys: ['playpause'] },
  { emoji: '⏭️', label: 'Next track', keys: ['nexttrack'] },
  { emoji: '⏮️', label: 'Previous', keys: ['prevtrack'] },
  { emoji: '🔉', label: 'Volume down', keys: ['volumedown'] },
  { emoji: '🔊', label: 'Volume up', keys: ['volumeup'] },
  { emoji: '🔇', label: 'Mute', keys: ['volumemute'] },
  { emoji: '💾', label: 'Save', keys: ['mod', 's'] },
  { emoji: '↩️', label: 'Undo', keys: ['mod', 'z'] },
  { emoji: '📋', label: 'Copy', keys: ['mod', 'c'] },
  { emoji: '📥', label: 'Paste', keys: ['mod', 'v'] },
  { emoji: '🔀', label: 'Switch app', keys: ['alt', 'tab'] },
  { emoji: '➕', label: 'New tab', keys: ['mod', 't'] },
];

const EMOJI_CHOICES = ['⭐', '🎮', '📺', '🎨', '📷', '🛒', '💬', '📰', '🎧', '🧠'];

/** Quick launch: open apps and websites on the PC with one tap. */
export function AppsScreen() {
  const { status, runAction, shortcuts, addShortcut, removeShortcut, showToast } = useApp();
  const connected = status === 'connected';
  const [adding, setAdding] = useState(false);
  const [label, setLabel] = useState('');
  const [target, setTarget] = useState('');
  const [emoji, setEmoji] = useState('⭐');

  const launch = (s: Pick<Shortcut, 'kind' | 'target' | 'label'>) =>
    s.kind === 'url' ? runAction('open_url', { url: s.target }, `Open ${s.label}`) : runAction('open_app', { name: s.target }, `Open ${s.label}`);

  const save = () => {
    const t = target.trim();
    const l = label.trim() || t;
    if (!t) return;
    const isUrl = /^(https?:\/\/|www\.)|\.[a-z]{2,}(\/|$)/i.test(t) && !t.includes(' ');
    addShortcut({ label: l, target: t, kind: isUrl ? 'url' : 'app', emoji });
    setLabel('');
    setTarget('');
    setAdding(false);
    showToast(`Added ${l}`, 'success');
  };

  const confirmRemove = (s: Shortcut) => {
    if (Platform.OS === 'web') {
      removeShortcut(s.id);
      return;
    }
    Alert.alert('Remove shortcut', `Remove "${s.label}"?`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Remove', style: 'destructive', onPress: () => removeShortcut(s.id) },
    ]);
  };

  return (
    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <View style={styles.header}>
        <Text style={font.title}>Quick Launch</Text>
        <StatusPill />
      </View>

      <SectionTitle>Apps on your PC</SectionTitle>
      <View style={styles.grid}>
        {APPS.map((a) => (
          <Tile key={a.label} emoji={a.emoji} label={a.label} disabled={!connected} onPress={() => launch({ kind: 'app', target: a.name, label: a.label })} />
        ))}
      </View>

      <SectionTitle>Websites</SectionTitle>
      <View style={styles.grid}>
        {SITES.map((s) => (
          <Tile key={s.label} emoji={s.emoji} label={s.label} color={colors.yellowSoft} disabled={!connected} onPress={() => launch({ kind: 'url', target: s.url, label: s.label })} />
        ))}
      </View>

      <SectionTitle right={<PillButton small tone="soft" label={adding ? 'Close' : 'Add'} emoji={adding ? undefined : '➕'} onPress={() => setAdding(!adding)} />}>My shortcuts</SectionTitle>
      {adding && (
        <Card style={{ marginBottom: 12 }}>
          <Text style={styles.label}>Name</Text>
          <TextInput value={label} onChangeText={setLabel} placeholder="e.g. Photoshop or News" placeholderTextColor={colors.faint} style={styles.input} />
          <Text style={styles.label}>App name or website</Text>
          <TextInput
            value={target}
            onChangeText={setTarget}
            placeholder="e.g. photoshop  or  news.ycombinator.com"
            placeholderTextColor={colors.faint}
            autoCapitalize="none"
            autoCorrect={false}
            style={styles.input}
          />
          <Text style={styles.label}>Icon</Text>
          <View style={styles.emojiRow}>
            {EMOJI_CHOICES.map((e) => (
              <Pressable key={e} onPress={() => setEmoji(e)} style={[styles.emojiChoice, e === emoji && styles.emojiActive]}>
                <Text style={{ fontSize: 22 }}>{e}</Text>
              </Pressable>
            ))}
          </View>
          <PillButton label="Save shortcut" onPress={save} disabled={!target.trim()} style={{ marginTop: 12 }} />
        </Card>
      )}
      {shortcuts.length === 0 && !adding ? (
        <Text style={styles.empty}>Add your own apps and sites here. Long-press a shortcut to remove it.</Text>
      ) : (
        <View style={styles.grid}>
          {shortcuts.map((s) => (
            <Tile key={s.id} emoji={s.emoji} label={s.label} color={colors.purpleSoft} disabled={!connected} onPress={() => launch(s)} onLongPress={() => confirmRemove(s)} />
          ))}
          {shortcuts.length % 3 !== 0 && <View style={{ width: '31%' }} />}
          {shortcuts.length % 3 === 1 && <View style={{ width: '31%' }} />}
        </View>
      )}

      <SectionTitle>Media & shortcuts</SectionTitle>
      <View style={styles.grid}>
        {KEYS.map((k) => (
          <Tile key={k.label} emoji={k.emoji} label={k.label} color={colors.greenSoft} disabled={!connected} onPress={() => runAction('keys', { keys: k.keys }, k.label)} />
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingBottom: 28 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between' },
  label: { fontSize: 13, fontWeight: '700', color: colors.muted, marginBottom: 6, marginTop: 8 },
  input: { borderRadius: radius.sm, backgroundColor: colors.bg, paddingHorizontal: 12, paddingVertical: 10, fontSize: 15, color: colors.text },
  emojiRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  emojiChoice: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg },
  emojiActive: { backgroundColor: colors.primarySoft, borderWidth: 2, borderColor: colors.primary },
  empty: { ...font.small, textAlign: 'center', paddingVertical: 8 },
});
