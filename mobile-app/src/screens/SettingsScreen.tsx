import { Directory, File, Paths } from 'expo-file-system';
import * as ImagePicker from 'expo-image-picker';
import { useState } from 'react';
import { Alert, Platform, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';

import { PROTOCOL_VERSION } from '../../../shared/protocol';
import { Avatar } from '../components/Avatar';
import { StatusPill } from '../components/StatusPill';
import { Card, PillButton, SectionTitle } from '../components/ui';
import { useApp } from '../state/AppContext';
import { colors, font, radius } from '../theme';

async function persistAvatar(uri: string, previous: string | null): Promise<string> {
  if (Platform.OS === 'web') return uri;
  try {
    const dir = new Directory(Paths.document, 'avatar');
    if (!dir.exists) dir.create({ intermediates: true });
    const dest = new File(dir, `avatar-${Date.now()}.jpg`);
    await new File(uri).copy(dest);
    if (previous) {
      try {
        const old = new File(previous);
        if (old.exists) old.delete();
      } catch {
        /* ignore */
      }
    }
    return dest.uri;
  } catch {
    return uri; // fall back to the picker's cache copy
  }
}

export function SettingsScreen() {
  const app = useApp();
  const { settings, updateSettings, pairing, pcConfig, status } = app;
  const connected = status === 'connected';

  const [groqKey, setGroqKey] = useState('');
  const [elevenKey, setElevenKey] = useState('');
  const [voiceIdEdit, setVoiceId] = useState<string | null>(null);
  const voiceId = voiceIdEdit ?? pcConfig?.elevenLabsVoiceId ?? '';
  const [host, setHost] = useState(pairing?.lastHost ?? pairing?.hosts[0] ?? '');
  const [port, setPort] = useState(String(pairing?.port ?? 8765));
  const [petName, setPetName] = useState(settings.petName);

  const saveKeys = () => {
    const changes: { groqApiKey?: string; elevenLabsApiKey?: string; elevenLabsVoiceId?: string } = {};
    if (groqKey.trim()) changes.groqApiKey = groqKey.trim();
    if (elevenKey.trim()) changes.elevenLabsApiKey = elevenKey.trim();
    if (voiceId.trim() && voiceId.trim() !== pcConfig?.elevenLabsVoiceId) changes.elevenLabsVoiceId = voiceId.trim();
    if (!Object.keys(changes).length) {
      app.showToast('Nothing to save: paste a key first');
      return;
    }
    if (app.updatePcConfig(changes)) {
      setGroqKey('');
      setElevenKey('');
      setVoiceId(null);
      app.showToast('Saved on your PC 🔒', 'success');
    }
  };

  const pickPhoto = async () => {
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, aspect: [1, 1], quality: 0.85 });
    if (res.canceled || !res.assets?.[0]) return;
    const uri = await persistAvatar(res.assets[0].uri, settings.avatarUri);
    updateSettings({ avatarUri: uri });
    app.sfx('bark');
    app.showToast('New look! 📸', 'success');
  };

  const forget = () => {
    const doIt = () => app.forgetPc();
    if (Platform.OS === 'web') doIt();
    else
      Alert.alert('Forget this PC?', 'You will need to scan the QR code again.', [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Forget', style: 'destructive', onPress: doIt },
      ]);
  };

  const keyStatus = (has: boolean | undefined) => (pcConfig ? (has ? '✅ set on PC' : '⚠️ not set') : '…');

  return (
    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <View style={styles.header}>
        <Text style={font.title}>Settings</Text>
        <StatusPill />
      </View>

      <SectionTitle icon="paw-outline">Companion</SectionTitle>
      <Card>
        <View style={styles.avatarRow}>
          <Avatar uri={settings.avatarUri} size={96} onPress={() => app.sfx('boop')} />
          <View style={{ flex: 1, marginLeft: 14 }}>
            <Text style={styles.label}>Name</Text>
            <TextInput
              value={petName}
              onChangeText={setPetName}
              onEndEditing={() => updateSettings({ petName: petName.trim() || 'Biscuit' })}
              onBlur={() => updateSettings({ petName: petName.trim() || 'Biscuit' })}
              maxLength={20}
              style={styles.input}
            />
          </View>
        </View>
        <View style={styles.row2}>
          <PillButton label="Choose photo" icon="images-outline" small onPress={() => void pickPhoto()} style={{ flex: 1 }} />
          <PillButton label="Use puppy" icon="paw-outline" tone="soft" small disabled={!settings.avatarUri} onPress={() => updateSettings({ avatarUri: null })} style={{ flex: 1 }} />
        </View>
        <Text style={styles.help}>Any photo works: it gets cute bounce, float and blink animations automatically.</Text>
      </Card>

      <SectionTitle icon="volume-medium-outline">Sound & voice</SectionTitle>
      <Card>
        <Toggle label="Sound effects" hint="Barks, boops and chimes" value={settings.soundEffects} onChange={(v) => updateSettings({ soundEffects: v })} />
        <Toggle label="Vibration" value={settings.haptics} onChange={(v) => updateSettings({ haptics: v })} />
        <Toggle label="ElevenLabs voice replies" hint="Generated on your PC" value={settings.voiceReplies} onChange={(v) => updateSettings({ voiceReplies: v })} />
        <Toggle label="Phone voice fallback" hint="Speak with the phone's voice if ElevenLabs is unavailable" value={settings.speakOnPhone} onChange={(v) => updateSettings({ speakOnPhone: v })} />
        <Toggle label="Chimes on the PC" value={pcConfig?.pcSounds ?? true} disabled={!connected} onChange={(v) => app.updatePcConfig({ pcSounds: v })} />
        <Toggle label="Blue cursor visible" value={pcConfig?.cursorVisible ?? true} disabled={!connected} onChange={(v) => app.updatePcConfig({ cursorVisible: v })} last />
      </Card>

      <SectionTitle icon="key-outline">AI keys (stored on your PC)</SectionTitle>
      <Card>
        <Text style={styles.label}>Groq API key · {keyStatus(pcConfig?.hasGroqKey)}</Text>
        <TextInput value={groqKey} onChangeText={setGroqKey} placeholder={pcConfig?.hasGroqKey ? '•••••••• (paste to replace)' : 'gsk_…'} placeholderTextColor={colors.faint} secureTextEntry autoCapitalize="none" autoCorrect={false} style={styles.input} />
        <Text style={styles.label}>ElevenLabs API key · {keyStatus(pcConfig?.hasElevenLabsKey)}</Text>
        <TextInput value={elevenKey} onChangeText={setElevenKey} placeholder={pcConfig?.hasElevenLabsKey ? '•••••••• (paste to replace)' : 'sk_…'} placeholderTextColor={colors.faint} secureTextEntry autoCapitalize="none" autoCorrect={false} style={styles.input} />
        <Text style={styles.label}>ElevenLabs voice ID</Text>
        <TextInput value={voiceId} onChangeText={setVoiceId} placeholder="cgSgspJ2msm6clMCkdW9" placeholderTextColor={colors.faint} autoCapitalize="none" autoCorrect={false} style={styles.input} />
        <PillButton label="Save to PC" icon="lock-closed-outline" onPress={saveKeys} disabled={!connected} style={{ marginTop: 14 }} />
        <Text style={styles.help}>
          Keys travel over your home Wi-Fi to the PC and are saved in pc-agent/.env. They are never stored on this phone.
          {pcConfig ? `\nModels: ${pcConfig.models.chat} · vision ${pcConfig.models.vision} · ${pcConfig.models.stt} · ${pcConfig.models.tts}` : ''}
        </Text>
      </Card>

      <SectionTitle icon="wifi-outline">Wi-Fi connection</SectionTitle>
      <Card>
        <Text style={styles.value}>{pairing ? `🖥️ ${pairing.pcName}` : 'Not paired'}</Text>
        <Text style={styles.help}>Addresses from the QR code: {pairing?.hosts.join(', ') ?? '-'}</Text>
        <View style={styles.row2}>
          <View style={{ flex: 3 }}>
            <Text style={styles.label}>PC address</Text>
            <TextInput value={host} onChangeText={setHost} placeholder="192.168.1.20" placeholderTextColor={colors.faint} autoCapitalize="none" autoCorrect={false} keyboardType="numbers-and-punctuation" style={styles.input} />
          </View>
          <View style={{ flex: 1.3 }}>
            <Text style={styles.label}>Port</Text>
            <TextInput value={port} onChangeText={setPort} keyboardType="number-pad" style={styles.input} />
          </View>
        </View>
        <View style={styles.row2}>
          <PillButton label="Connect" small onPress={() => app.setManualHost(host.trim(), Number(port) || 8765)} disabled={!host.trim()} style={{ flex: 1 }} />
          <PillButton label="Retry" small tone="soft" onPress={app.reconnect} style={{ flex: 1 }} />
        </View>
        <PillButton label="Forget PC & scan a new QR" tone="danger" small onPress={forget} style={{ marginTop: 10 }} />
      </Card>

      <Text style={styles.about}>Desktop Friend 1.1.0 · protocol v{PROTOCOL_VERSION}</Text>
    </ScrollView>
  );
}

function Toggle({ label, hint, value, onChange, disabled, last }: { label: string; hint?: string; value: boolean; onChange: (v: boolean) => void; disabled?: boolean; last?: boolean }) {
  return (
    <View style={[styles.toggle, !last && styles.toggleBorder]}>
      <View style={{ flex: 1, paddingRight: 10 }}>
        <Text style={[styles.toggleLabel, disabled && { color: colors.faint }]}>{label}</Text>
        {hint ? <Text style={styles.toggleHint}>{hint}</Text> : null}
      </View>
      <Switch value={value} onValueChange={onChange} disabled={disabled} trackColor={{ true: colors.primary, false: colors.bgDeep }} thumbColor="#fff" />
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingBottom: 32 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  avatarRow: { flexDirection: 'row', alignItems: 'center' },
  row2: { flexDirection: 'row', gap: 10, marginTop: 10 },
  label: { fontSize: 13, fontWeight: '700', color: colors.muted, marginBottom: 6, marginTop: 10 },
  value: { fontSize: 16, fontWeight: '800', color: colors.text },
  input: { borderRadius: radius.sm, backgroundColor: colors.bg, paddingHorizontal: 12, paddingVertical: 10, fontSize: 15, color: colors.text },
  help: { ...font.small, marginTop: 10, lineHeight: 18 },
  toggle: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10 },
  toggleBorder: { borderBottomWidth: 1, borderBottomColor: colors.bg },
  toggleLabel: { fontSize: 15, fontWeight: '700', color: colors.text },
  toggleHint: { fontSize: 12.5, color: colors.muted, marginTop: 2 },
  about: { ...font.small, textAlign: 'center', marginTop: 24 },
});
