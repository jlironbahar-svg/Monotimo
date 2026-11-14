import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Alert, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { StatusPill } from '../components/StatusPill';
import { Card, Chip, Icon, PillButton, SectionTitle, Tile, type IconName } from '../components/ui';
import { useApp, type Shortcut } from '../state/AppContext';
import { colors, font, radius, shadow } from '../theme';

const CLAUDE_ORANGE = '#D97757';

type Launcher = { label: string; icon: IconName; tint: string; kind: 'app' | 'url'; target: string; sub?: string };

const PC_APPS: Launcher[] = [
  { label: 'Claude', icon: 'sparkles', tint: CLAUDE_ORANGE, kind: 'app', target: 'claude', sub: 'Desktop app' },
  { label: 'ChatGPT', icon: 'chatbubbles-outline', tint: '#10A37F', kind: 'app', target: 'chatgpt' },
  { label: 'Browser', icon: 'globe-outline', tint: colors.primary, kind: 'app', target: 'browser' },
  { label: 'Files', icon: 'folder-open-outline', tint: '#E0A800', kind: 'app', target: 'file explorer' },
  { label: 'Notepad', icon: 'document-text-outline', tint: '#5B6B8C', kind: 'app', target: 'notepad' },
  { label: 'Calculator', icon: 'calculator-outline', tint: '#7A5AF8', kind: 'app', target: 'calculator' },
  { label: 'Terminal', icon: 'terminal-outline', tint: '#1B2A4A', kind: 'app', target: 'terminal' },
  { label: 'VS Code', icon: 'code-slash-outline', tint: '#007ACC', kind: 'app', target: 'vs code' },
  { label: 'Spotify', icon: 'musical-notes-outline', tint: '#1DB954', kind: 'app', target: 'spotify' },
  { label: 'Discord', icon: 'logo-discord', tint: '#5865F2', kind: 'app', target: 'discord' },
  { label: 'WhatsApp', icon: 'logo-whatsapp', tint: '#25D366', kind: 'app', target: 'whatsapp' },
  { label: 'Settings', icon: 'settings-outline', tint: '#6B7A99', kind: 'app', target: 'settings' },
];

const SITES: Launcher[] = [
  { label: 'Claude.ai', icon: 'sparkles-outline', tint: CLAUDE_ORANGE, kind: 'url', target: 'https://claude.ai' },
  { label: 'YouTube', icon: 'logo-youtube', tint: '#FF0000', kind: 'url', target: 'https://www.youtube.com' },
  { label: 'Gmail', icon: 'mail-outline', tint: '#EA4335', kind: 'url', target: 'https://mail.google.com' },
  { label: 'GitHub', icon: 'logo-github', tint: '#1B2A4A', kind: 'url', target: 'https://github.com' },
  { label: 'Maps', icon: 'map-outline', tint: '#34A853', kind: 'url', target: 'https://maps.google.com' },
  { label: 'Netflix', icon: 'film-outline', tint: '#E50914', kind: 'url', target: 'https://www.netflix.com' },
];

const SHORTCUT_GROUPS: { title: string; icon: IconName; tint: string; items: { name: string; label: string; icon: IconName }[] }[] = [
  {
    title: 'Media',
    icon: 'musical-notes-outline',
    tint: colors.pink,
    items: [
      { name: 'play_pause', label: 'Play / Pause', icon: 'play' },
      { name: 'prev_track', label: 'Previous', icon: 'play-skip-back' },
      { name: 'next_track', label: 'Next', icon: 'play-skip-forward' },
      { name: 'volume_down', label: 'Vol −', icon: 'volume-low' },
      { name: 'volume_up', label: 'Vol +', icon: 'volume-high' },
      { name: 'mute', label: 'Mute', icon: 'volume-mute' },
    ],
  },
  {
    title: 'Editing',
    icon: 'create-outline',
    tint: colors.primary,
    items: [
      { name: 'copy', label: 'Copy', icon: 'copy-outline' },
      { name: 'paste', label: 'Paste', icon: 'clipboard-outline' },
      { name: 'cut', label: 'Cut', icon: 'cut-outline' },
      { name: 'undo', label: 'Undo', icon: 'arrow-undo' },
      { name: 'redo', label: 'Redo', icon: 'arrow-redo' },
      { name: 'select_all', label: 'Select all', icon: 'albums-outline' },
      { name: 'save', label: 'Save', icon: 'save-outline' },
      { name: 'find', label: 'Find', icon: 'search-outline' },
    ],
  },
  {
    title: 'Browser & tabs',
    icon: 'browsers-outline',
    tint: '#E0A800',
    items: [
      { name: 'new_tab', label: 'New tab', icon: 'add-circle-outline' },
      { name: 'close_tab', label: 'Close tab', icon: 'close-circle-outline' },
      { name: 'reopen_tab', label: 'Reopen tab', icon: 'reload-outline' },
      { name: 'next_tab', label: 'Next tab', icon: 'chevron-forward' },
      { name: 'back', label: 'Back', icon: 'arrow-back-outline' },
      { name: 'refresh', label: 'Refresh', icon: 'refresh' },
      { name: 'zoom_in', label: 'Zoom in', icon: 'add-outline' },
      { name: 'zoom_out', label: 'Zoom out', icon: 'remove-outline' },
    ],
  },
  {
    title: 'Windows & system',
    icon: 'grid-outline',
    tint: colors.green,
    items: [
      { name: 'switch_app', label: 'Switch app', icon: 'swap-horizontal' },
      { name: 'show_desktop', label: 'Desktop', icon: 'desktop-outline' },
      { name: 'task_view', label: 'All windows', icon: 'layers-outline' },
      { name: 'minimize', label: 'Minimize', icon: 'contract-outline' },
      { name: 'fullscreen', label: 'Fullscreen', icon: 'expand-outline' },
      { name: 'close_window', label: 'Close window', icon: 'close-circle-outline' },
      { name: 'screenshot', label: 'Screenshot', icon: 'crop-outline' },
      { name: 'search', label: 'Search', icon: 'search-outline' },
      { name: 'emoji', label: 'Emoji', icon: 'happy-outline' },
      { name: 'lock', label: 'Lock PC', icon: 'lock-closed-outline' },
    ],
  },
];

const EMOJI_CHOICES = ['⭐', '🎮', '📺', '🎨', '📷', '🛒', '💬', '📰', '🎧', '🧠'];

/** Quick launch: open apps and websites on the PC with one tap. */
export function AppsScreen() {
  const { status, runAction, shortcuts, addShortcut, removeShortcut, showToast, pcApps, requestApps, pairing } = useApp();
  const connected = status === 'connected';
  const [adding, setAdding] = useState(false);
  const [label, setLabel] = useState('');
  const [target, setTarget] = useState('');
  const [emoji, setEmoji] = useState('⭐');
  const [query, setQuery] = useState('');
  const [showAll, setShowAll] = useState(false);

  // fetch the PC's installed apps once we're connected
  useEffect(() => {
    if (connected && pcApps === null) requestApps();
  }, [connected, pcApps, requestApps]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = pcApps ?? [];
    return q ? list.filter((a) => a.toLowerCase().includes(q)) : list;
  }, [pcApps, query]);
  const visible = showAll || query ? filtered.slice(0, 120) : filtered.slice(0, 8);

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

  const pin = (name: string) => {
    if (shortcuts.some((s) => s.kind === 'app' && s.target === name)) {
      showToast(`${name} is already in My shortcuts`);
      return;
    }
    addShortcut({ label: name, target: name, kind: 'app', emoji: '⭐' });
    showToast(`Pinned ${name} to My shortcuts`, 'success');
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
        <View style={{ flex: 1 }}>
          <Text style={font.title}>Apps</Text>
          <Text style={styles.subtitle}>Open anything on {pairing?.pcName ?? 'your PC'} with one tap</Text>
        </View>
        <StatusPill />
      </View>

      {/* Claude, featured */}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Open Claude on the PC"
        disabled={!connected}
        onPress={() => launch({ kind: 'app', target: 'claude', label: 'Claude' })}
        style={({ pressed }) => [styles.feature, { opacity: connected ? 1 : 0.5, transform: [{ scale: pressed ? 0.98 : 1 }] }]}
      >
        <View style={styles.featureBadge}>
          <Icon name="sparkles" size={26} color="#fff" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.featureTitle}>Open Claude</Text>
          <Text style={styles.featureText}>{"Launches the Claude desktop app, or claude.ai if it isn't installed"}</Text>
        </View>
        <Icon name="chevron-forward" size={22} color={CLAUDE_ORANGE} />
      </Pressable>

      <SectionTitle icon="desktop-outline">Apps on your PC</SectionTitle>
      <View style={styles.grid}>
        {PC_APPS.map((a) => (
          <Tile key={a.label} icon={a.icon} tint={a.tint} label={a.label} sublabel={a.sub} disabled={!connected} onPress={() => launch(a)} />
        ))}
      </View>

      <SectionTitle icon="globe-outline">Websites</SectionTitle>
      <View style={styles.grid}>
        {SITES.map((s) => (
          <Tile key={s.label} icon={s.icon} tint={s.tint} label={s.label} disabled={!connected} onPress={() => launch(s)} />
        ))}
      </View>

      <SectionTitle
        icon="apps-outline"
        right={
          connected ? (
            <Pressable onPress={requestApps} hitSlop={10} accessibilityLabel="Refresh app list">
              <Icon name="refresh" size={18} color={colors.muted} />
            </Pressable>
          ) : undefined
        }
      >
        {`Everything on ${pairing?.pcName ?? 'your PC'}`}
      </SectionTitle>
      <Card style={{ paddingVertical: 8 }}>
        <View style={styles.searchRow}>
          <Icon name="search-outline" size={18} color={colors.muted} />
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder={pcApps ? `Search ${pcApps.length} installed apps` : 'Search installed apps'}
            placeholderTextColor={colors.faint}
            style={styles.search}
            autoCorrect={false}
          />
        </View>
        {!connected ? (
          <Text style={styles.empty}>Connect to your PC to see its apps.</Text>
        ) : pcApps === null ? (
          <ActivityIndicator color={colors.primary} style={{ marginVertical: 14 }} />
        ) : filtered.length === 0 ? (
          <Text style={styles.empty}>{query ? `No app matches "${query}". Tap below to try opening it anyway.` : 'No apps found on the PC.'}</Text>
        ) : (
          visible.map((name) => (
            <Pressable
              key={name}
              onPress={() => runAction('open_app', { name }, `Open ${name}`)}
              onLongPress={() => pin(name)}
              style={({ pressed }) => [styles.appRow, pressed && { backgroundColor: colors.bg }]}
              accessibilityRole="button"
              accessibilityLabel={`Open ${name}`}
            >
              <View style={styles.appInitial}>
                <Text style={styles.appInitialText}>{name.slice(0, 1).toUpperCase()}</Text>
              </View>
              <Text style={styles.appName} numberOfLines={1}>
                {name}
              </Text>
              <Icon name="open-outline" size={17} color={colors.faint} />
            </Pressable>
          ))
        )}
        {connected && query.trim() && filtered.length === 0 ? (
          <PillButton label={`Open "${query.trim()}"`} icon="rocket-outline" small tone="soft" onPress={() => runAction('open_app', { name: query.trim() }, `Open ${query.trim()}`)} style={{ marginVertical: 8 }} />
        ) : null}
        {!query && filtered.length > 8 ? (
          <Pressable onPress={() => setShowAll(!showAll)} style={styles.more} hitSlop={6}>
            <Text style={styles.moreText}>{showAll ? 'Show less' : `Show all ${filtered.length} apps`}</Text>
          </Pressable>
        ) : null}
        {pcApps?.length ? <Text style={styles.hint}>Tip: long-press an app to pin it to My shortcuts.</Text> : null}
      </Card>

      <SectionTitle icon="star-outline" right={<PillButton small tone="soft" label={adding ? 'Close' : 'Add'} icon={adding ? undefined : 'add-outline'} onPress={() => setAdding(!adding)} />}>
        My shortcuts
      </SectionTitle>
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
        <Text style={styles.empty}>Add your own apps and sites here, or long-press any app above. Long-press a shortcut to remove it.</Text>
      ) : (
        <View style={styles.grid}>
          {shortcuts.map((s) => (
            <Tile key={s.id} emoji={s.emoji} label={s.label} color={colors.purpleSoft} disabled={!connected} onPress={() => launch(s)} onLongPress={() => confirmRemove(s)} />
          ))}
          {shortcuts.length % 3 !== 0 && <View style={{ width: '31.5%' }} />}
          {shortcuts.length % 3 === 1 && <View style={{ width: '31.5%' }} />}
        </View>
      )}

      {SHORTCUT_GROUPS.map((g) => (
        <View key={g.title}>
          <SectionTitle icon={g.icon}>{g.title}</SectionTitle>
          <View style={styles.chips}>
            {g.items.map((k) => (
              <Chip key={k.name} label={k.label} icon={k.icon} tint={g.tint} disabled={!connected} onPress={() => runAction('shortcut', { name: k.name }, k.label)} />
            ))}
          </View>
        </View>
      ))}
      <Text style={styles.footnote}>Shortcuts use the right keys for your PC automatically (Ctrl on Windows and Linux, ⌘ on Mac).</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingBottom: 28 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  subtitle: { ...font.small, marginTop: 2 },
  feature: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    marginTop: 16,
    padding: 16,
    borderRadius: radius.lg,
    backgroundColor: '#FFF3EE',
    borderWidth: 1,
    borderColor: '#F6D3C4',
  },
  featureBadge: { width: 50, height: 50, borderRadius: 16, backgroundColor: CLAUDE_ORANGE, alignItems: 'center', justifyContent: 'center', ...shadow },
  featureTitle: { fontSize: 17, fontWeight: '800', color: colors.text },
  featureText: { fontSize: 13, color: colors.muted, marginTop: 2 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between' },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.bg, borderRadius: radius.pill, paddingHorizontal: 14, marginVertical: 6 },
  search: { flex: 1, paddingVertical: 10, fontSize: 15, color: colors.text },
  appRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10, paddingHorizontal: 6, borderRadius: radius.sm },
  appInitial: { width: 34, height: 34, borderRadius: 10, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' },
  appInitialText: { fontWeight: '800', color: colors.primaryDark },
  appName: { flex: 1, fontSize: 15, fontWeight: '600', color: colors.text },
  more: { alignItems: 'center', paddingVertical: 10 },
  moreText: { color: colors.primary, fontWeight: '800' },
  hint: { ...font.small, fontSize: 12, textAlign: 'center', paddingBottom: 6 },
  chips: { flexDirection: 'row', flexWrap: 'wrap' },
  label: { fontSize: 13, fontWeight: '700', color: colors.muted, marginBottom: 6, marginTop: 8 },
  input: { borderRadius: radius.sm, backgroundColor: colors.bg, paddingHorizontal: 12, paddingVertical: 10, fontSize: 15, color: colors.text },
  emojiRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  emojiChoice: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg },
  emojiActive: { backgroundColor: colors.primarySoft, borderWidth: 2, borderColor: colors.primary },
  empty: { ...font.small, textAlign: 'center', paddingVertical: 10 },
  footnote: { ...font.small, fontSize: 12, textAlign: 'center', marginTop: 12 },
});
