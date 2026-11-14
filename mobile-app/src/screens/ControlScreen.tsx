import { useRef, useState, type ComponentRef } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import type { QuickAction } from '../../../shared/protocol';
import { Avatar } from '../components/Avatar';
import { FloatingEmojis } from '../components/FloatingEmojis';
import { PushToTalk } from '../components/PushToTalk';
import { SpeechBubble } from '../components/SpeechBubble';
import { StatusPill } from '../components/StatusPill';
import { Card, SectionTitle, Tile } from '../components/ui';
import { useApp, type ChatEntry } from '../state/AppContext';
import { colors, font, radius, shadow } from '../theme';

type Pending = { action: QuickAction; prompt: string; argName: string; label: (v: string) => string };

const NEEDS_TEXT: Record<string, Pending> = {
  point: { action: 'point', prompt: 'What should I point at? e.g. "the save button"', argName: 'target', label: (v) => `Point at ${v}` },
  click: { action: 'click', prompt: 'What should I click? e.g. "the Play button"', argName: 'target', label: (v) => `Click ${v}` },
  type: { action: 'type', prompt: 'What should I type on the PC?', argName: 'text', label: (v) => `Type "${v}"` },
  web_search: { action: 'web_search', prompt: 'What should I search the web for?', argName: 'query', label: (v) => `Search the web for ${v}` },
};

const TOOL_LABEL: Record<string, string> = {
  point_at: '👉 pointed',
  point: '👉 pointed',
  click: '🖱️ clicked',
  scroll: '📜 scrolled',
  type_text: '⌨️ typed',
  type: '⌨️ typed',
  press_keys: '⌨️ keys',
  keys: '⌨️ keys',
  open_app: '🚀 opened app',
  open_website: '🌐 opened site',
  open_url: '🌐 opened site',
  web_search: '🔍 searched',
  look_at_screen: '👀 looked',
  describe_screen: '👀 looked',
  cursor_home: '🏠 cursor home',
  toggle_cursor: '🙈 cursor',
};

/** Web & PC control: quick actions, push-to-talk and a typing box. */
export function ControlScreen() {
  const app = useApp();
  const { status, pcState, messages, settings, reactionMood, talking, burst, screenshot, pcConfig } = app;
  const [text, setText] = useState('');
  const [pending, setPending] = useState<Pending | null>(null);
  const inputRef = useRef<ComponentRef<typeof TextInput>>(null);
  const connected = status === 'connected';

  const lastFriend = [...messages].reverse().find((m) => m.from === 'friend');
  const busy = pcState.state !== 'idle';
  const bubble = busy ? pcState.detail || 'Thinking…' : lastFriend?.text ?? 'Tell me what to do on your PC! Try "point at the start button".';

  const startPending = (key: keyof typeof NEEDS_TEXT) => {
    setPending(NEEDS_TEXT[key]);
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  const submit = () => {
    const value = text.trim();
    if (!value) return;
    if (pending) app.runAction(pending.action, { [pending.argName]: value }, pending.label(value));
    else app.sendChat(value);
    setText('');
    setPending(null);
  };

  return (
    <View style={{ flex: 1 }}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <View style={styles.header}>
          <Text style={font.title}>PC Control</Text>
          <StatusPill />
        </View>

        <View style={styles.friendRow}>
          <View style={styles.avatarBox}>
            <Avatar uri={settings.avatarUri} size={104} mood={reactionMood ?? (busy ? 'curious' : 'happy')} talking={talking} onPress={() => app.sfx('bark')} />
            <FloatingEmojis burst={burst} count={4} height={140} />
          </View>
          <View style={{ flex: 1 }}>
            <SpeechBubble text={bubble} tone={busy ? 'thinking' : 'friend'} maxLines={6} />
          </View>
        </View>

        {pcConfig && !pcConfig.hasGroqKey && (
          <Card style={styles.warn}>
            <Text style={styles.warnText}>{'🔑 Add a Groq API key in Settings so I can chat, hear you and see your screen. Simple commands like "open notepad" already work.'}</Text>
          </Card>
        )}

        {screenshot && (
          <Card style={styles.shotCard}>
            <View style={styles.shotHeader}>
              <Text style={font.h2}>📸 Your screen</Text>
              <Pressable onPress={app.clearScreenshot} hitSlop={12}>
                <Text style={styles.close}>✕</Text>
              </Pressable>
            </View>
            <Image source={{ uri: `data:image/jpeg;base64,${screenshot.image}` }} style={{ width: '100%', aspectRatio: screenshot.width / screenshot.height, borderRadius: radius.sm }} resizeMode="contain" />
          </Card>
        )}

        <SectionTitle icon="flash-outline">Quick actions</SectionTitle>
        <View style={styles.grid}>
          <Tile icon="eye-outline" tint={colors.primary} label="What's on screen?" disabled={!connected} onPress={() => app.runAction('describe_screen', {}, "What's on my screen?")} />
          <Tile icon="navigate-outline" tint={colors.pink} label="Point at…" disabled={!connected} onPress={() => startPending('point')} />
          <Tile icon="hand-left-outline" tint={colors.pink} label="Click…" disabled={!connected} onPress={() => startPending('click')} />
          <Tile icon="keypad-outline" tint="#E0A800" label="Type…" disabled={!connected} onPress={() => startPending('type')} />
          <Tile icon="search-outline" tint="#E0A800" label="Search web…" disabled={!connected} onPress={() => startPending('web_search')} />
          <Tile icon="camera-outline" tint={colors.primary} label="Peek at screen" disabled={!connected} onPress={app.requestScreenshot} />
          <Tile icon="arrow-up-circle-outline" tint={colors.green} label="Scroll up" disabled={!connected} onPress={() => app.runAction('scroll', { direction: 'up', amount: 5 }, 'Scroll up')} />
          <Tile icon="arrow-down-circle-outline" tint={colors.green} label="Scroll down" disabled={!connected} onPress={() => app.runAction('scroll', { direction: 'down', amount: 5 }, 'Scroll down')} />
          <Tile icon="home-outline" tint={colors.purple} label="Cursor home" disabled={!connected} onPress={() => app.runAction('cursor_home', {}, 'Cursor home')} />
        </View>

        <View style={styles.ptt}>
          <PushToTalk disabled={!connected} />
        </View>

        {messages.length > 0 && <SectionTitle icon="chatbubbles-outline">Conversation</SectionTitle>}
        {messages.slice(-16).map((m) => (
          <ChatRow key={m.id + m.from} entry={m} />
        ))}
      </ScrollView>

      <View style={styles.composer}>
        {pending && (
          <View style={styles.pendingRow}>
            <Text style={styles.pendingText} numberOfLines={1}>
              {pending.prompt}
            </Text>
            <Pressable onPress={() => setPending(null)} hitSlop={10}>
              <Text style={styles.close}>✕</Text>
            </Pressable>
          </View>
        )}
        <View style={styles.inputRow}>
          <TextInput
            ref={inputRef}
            value={text}
            onChangeText={setText}
            onSubmitEditing={submit}
            placeholder={pending ? 'Type here…' : 'Type a command… e.g. "open notepad"'}
            placeholderTextColor={colors.faint}
            returnKeyType="send"
            style={styles.input}
            editable={connected}
          />
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Send"
            onPress={submit}
            disabled={!text.trim() || !connected}
            style={({ pressed }) => [styles.send, { opacity: !text.trim() || !connected ? 0.4 : 1, transform: [{ scale: pressed ? 0.92 : 1 }] }]}
          >
            <Text style={styles.sendText}>➤</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

function ChatRow({ entry }: { entry: ChatEntry }) {
  const mine = entry.from === 'me';
  return (
    <View style={[styles.chatRow, mine ? styles.mineRow : styles.friendRowMsg]}>
      <View style={[styles.chatBubble, mine ? styles.mine : styles.theirs]}>
        <Text style={[styles.chatText, mine && { color: '#fff' }]}>
          {entry.text}
          {entry.pending ? '  ⏳' : ''}
        </Text>
        {!!entry.actions?.length && (
          <View style={styles.chips}>
            {entry.actions.map((a, i) => (
              <View key={i} style={[styles.chip, { backgroundColor: a.ok ? colors.greenSoft : colors.redSoft }]}>
                <Text style={styles.chipText}>
                  {TOOL_LABEL[a.tool] ?? a.tool} {a.ok ? '✓' : '✗'}
                </Text>
              </View>
            ))}
          </View>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingBottom: 20 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  friendRow: { flexDirection: 'row', alignItems: 'center', marginTop: 12 },
  avatarBox: { width: 118, alignItems: 'center' },
  warn: { marginTop: 12, backgroundColor: colors.yellowSoft },
  warnText: { color: '#7A5200', fontSize: 13.5, fontWeight: '600' },
  shotCard: { marginTop: 12 },
  shotHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  close: { fontSize: 18, color: colors.muted, fontWeight: '800' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between' },
  ptt: { alignItems: 'center', marginTop: 4 },
  chatRow: { flexDirection: 'row', marginVertical: 4 },
  mineRow: { justifyContent: 'flex-end' },
  friendRowMsg: { justifyContent: 'flex-start' },
  chatBubble: { maxWidth: '82%', borderRadius: radius.md, paddingHorizontal: 14, paddingVertical: 10 },
  mine: { backgroundColor: colors.primary, borderBottomRightRadius: 6 },
  theirs: { backgroundColor: colors.card, borderBottomLeftRadius: 6, ...shadow },
  chatText: { fontSize: 15, color: colors.text, lineHeight: 20 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 6, gap: 6 },
  chip: { borderRadius: radius.pill, paddingHorizontal: 8, paddingVertical: 3 },
  chipText: { fontSize: 11.5, fontWeight: '700', color: colors.text },
  composer: { paddingHorizontal: 12, paddingTop: 8, paddingBottom: 4, backgroundColor: colors.bg, borderTopWidth: 1, borderTopColor: colors.bgDeep },
  pendingRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.primarySoft, borderRadius: radius.sm, paddingHorizontal: 12, paddingVertical: 6, marginBottom: 6 },
  pendingText: { flex: 1, color: colors.primaryDark, fontWeight: '700', fontSize: 13 },
  inputRow: { flexDirection: 'row', alignItems: 'center' },
  input: { flex: 1, backgroundColor: colors.card, borderRadius: radius.pill, paddingHorizontal: 18, paddingVertical: 12, fontSize: 15, color: colors.text, ...shadow },
  send: { width: 48, height: 48, borderRadius: 24, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center', marginLeft: 8 },
  sendText: { color: '#fff', fontSize: 20, fontWeight: '800' },
});
