import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { ActivityIndicator, BackHandler, KeyboardAvoidingView, StyleSheet, View } from 'react-native';
import { SafeAreaProvider, useSafeAreaInsets } from 'react-native-safe-area-context';

import { ConnectionBanner } from './src/components/ConnectionBanner';
import { ModeBar, type Mode } from './src/components/ModeBar';
import { Toast } from './src/components/Toast';
import { AppsScreen } from './src/screens/AppsScreen';
import { ControlScreen } from './src/screens/ControlScreen';
import { SettingsScreen } from './src/screens/SettingsScreen';
import { SetupScreen } from './src/screens/SetupScreen';
import { TamagotchiScreen } from './src/screens/TamagotchiScreen';
import { AppProvider, useApp } from './src/state/AppContext';
import { colors } from './src/theme';

function Main() {
  const { ready, pairing } = useApp();
  const insets = useSafeAreaInsets();
  const [mode, setMode] = useState<Mode>('pet');

  // Android back button: go back to the pet first, exit only from there.
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (mode !== 'pet') {
        setMode('pet');
        return true;
      }
      return false;
    });
    return () => sub.remove();
  }, [mode]);

  if (!ready) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  // Not paired yet (or the pairing hasn't completed): show onboarding.
  if (!pairing?.deviceToken) return <SetupScreen />;

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ConnectionBanner />
      {/* Edge-to-edge apps don't get resized by the keyboard; "padding" measures the real overlap on both platforms. */}
      <KeyboardAvoidingView style={{ flex: 1 }} behavior="padding">
        {mode === 'pet' && <TamagotchiScreen />}
        {mode === 'control' && <ControlScreen />}
        {mode === 'apps' && <AppsScreen />}
        {mode === 'settings' && <SettingsScreen />}
      </KeyboardAvoidingView>
      <ModeBar mode={mode} onChange={setMode} />
    </View>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <AppProvider>
        <StatusBar style="dark" />
        <Main />
        <Toast />
      </AppProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg },
});
