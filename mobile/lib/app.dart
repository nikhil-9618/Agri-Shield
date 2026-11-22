import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'core/strings.dart';
import 'core/theme.dart';
import 'models/models.dart';
import 'providers.dart';
import 'screens/about_screen.dart';
import 'screens/alerts_screen.dart';
import 'screens/analysis_screen.dart';
import 'screens/camera_screen.dart';
import 'screens/help_screen.dart';
import 'screens/history_screen.dart';
import 'screens/home_screen.dart';
import 'screens/language_screen.dart';
import 'screens/profile_screen.dart';
import 'screens/result_screen.dart';
import 'screens/server_screen.dart';
import 'screens/splash_screen.dart';
import 'screens/voice_screen.dart';
import 'screens/weather_screen.dart';
import 'screens/welcome_screen.dart';

GoRouter buildRouter(String initialLocation) => GoRouter(
      initialLocation: initialLocation,
      routes: [
        GoRoute(path: '/splash', builder: (_, _) => const SplashScreen()),
        GoRoute(path: '/language', builder: (_, _) => const LanguageScreen()),
        GoRoute(path: '/about', builder: (_, _) => const AboutScreen()),
        GoRoute(path: '/welcome', builder: (_, _) => const WelcomeScreen()),
        ShellRoute(
          builder: (context, state, child) => AppShell(state: state, child: child),
          routes: [
            GoRoute(path: '/home', builder: (_, _) => const HomeScreen()),
            GoRoute(path: '/voice', builder: (_, _) => const VoiceScreen()),
            GoRoute(path: '/weather', builder: (_, _) => const WeatherScreen()),
            GoRoute(path: '/help', builder: (_, _) => const HelpScreen()),
          ],
        ),
        GoRoute(path: '/camera', builder: (_, _) => const CameraScreen()),
        GoRoute(
          path: '/analysis',
          builder: (_, state) => AnalysisScreen(imagePath: state.extra as String? ?? ''),
        ),
        GoRoute(
          path: '/result',
          builder: (_, state) => ResultScreen(
            diagnosis: state.extra is Diagnosis ? state.extra as Diagnosis : null,
          ),
        ),
        GoRoute(path: '/history', builder: (_, _) => const HistoryScreen()),
        GoRoute(path: '/alerts', builder: (_, _) => const AlertsScreen()),
        GoRoute(path: '/profile', builder: (_, _) => const ProfileScreen()),
        GoRoute(path: '/server', builder: (_, _) => const ServerScreen()),
      ],
    );

class AgriShieldApp extends ConsumerStatefulWidget {
  final String initialRoute;
  const AgriShieldApp({super.key, required this.initialRoute});

  @override
  ConsumerState<AgriShieldApp> createState() => _AgriShieldAppState();
}

class _AgriShieldAppState extends ConsumerState<AgriShieldApp> {
  late final GoRouter _router = buildRouter(widget.initialRoute);

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'AgriShield',
      debugShowCheckedModeBanner: false,
      theme: AgriTheme.build(),
      routerConfig: _router,
      builder: (context, child) {
        // Readability first: never let the system font scale break big buttons.
        final scale = MediaQuery.textScalerOf(context).clamp(
          minScaleFactor: 0.9,
          maxScaleFactor: 1.3,
        );
        return MediaQuery(
          data: MediaQuery.of(context).copyWith(textScaler: scale),
          child: child!,
        );
      },
    );
  }
}

class AppShell extends ConsumerWidget {
  final GoRouterState state;
  final Widget child;

  const AppShell({super.key, required this.state, required this.child});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lang = ref.watch(appProvider.select((s) => s.language));
    final path = state.uri.path;
    final index = switch (path) {
      '/voice' => 1,
      '/weather' => 2,
      '/help' => 3,
      _ => 0,
    };

    return Scaffold(
      body: SafeArea(child: child),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (i) {
          final target = switch (i) {
            1 => '/voice',
            2 => '/weather',
            3 => '/help',
            _ => '/home',
          };
          if (target != path) context.go(target);
        },
        destinations: [
          NavigationDestination(
            icon: const Icon(Icons.home_rounded, size: 30),
            selectedIcon: const Icon(Icons.home_rounded, size: 32),
            label: L.t(lang, 'navHome'),
          ),
          NavigationDestination(
            icon: const Icon(Icons.mic_rounded, size: 30),
            selectedIcon: const Icon(Icons.mic_rounded, size: 32),
            label: L.t(lang, 'navVoice'),
          ),
          NavigationDestination(
            icon: const Icon(Icons.cloud_rounded, size: 30),
            selectedIcon: const Icon(Icons.cloud_rounded, size: 32),
            label: L.t(lang, 'navWeather'),
          ),
          NavigationDestination(
            icon: const Icon(Icons.help_rounded, size: 30),
            selectedIcon: const Icon(Icons.help_rounded, size: 32),
            label: L.t(lang, 'navMore'),
          ),
        ],
      ),
    );
  }
}
