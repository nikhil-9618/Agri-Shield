import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/strings.dart';
import '../core/theme.dart';
import '../core/weather_loader.dart';
import '../models/models.dart';
import '../providers.dart';
import '../widgets/common.dart';

class AlertsScreen extends ConsumerStatefulWidget {
  const AlertsScreen({super.key});

  @override
  ConsumerState<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends ConsumerState<AlertsScreen> {
  WeatherSnapshot? _snapshot;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _snapshot = ref.read(appProvider.notifier).cachedWeather();
    Future.microtask(_load);
  }

  Future<void> _load() async {
    if (_loading) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    final lang = ref.read(appProvider).language;
    try {
      final snapshot = await loadWeatherForDevice(ref.read(apiProvider), lang);
      await ref.read(appProvider.notifier).cacheWeather(snapshot);
      if (!mounted) return;
      setState(() {
        _snapshot = snapshot;
        _loading = false;
      });
    } on LocationUnavailable {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = L.t(lang, 'needLocation');
      });
    } on WeatherUnavailable {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = L.t(lang, 'weatherOffline');
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = L.t(lang, 'commonError');
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final lang = ref.watch(appProvider.select((s) => s.language));
    final alerts = _snapshot?.alerts ?? const <WeatherAlert>[];

    return Scaffold(
      appBar: AppBar(
        title: Text(L.t(lang, 'alertsTitle')),
        actions: [
          IconButton(
            onPressed: _load,
            iconSize: 30,
            icon: _loading
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(color: Colors.white, strokeWidth: 3),
                  )
                : const Icon(Icons.refresh_rounded),
          ),
          const SizedBox(width: 6),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (alerts.isEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 40),
              child: Column(
                children: [
                  const Icon(Icons.notifications_none_rounded,
                      size: 96, color: AgriColors.healthy),
                  const SizedBox(height: 12),
                  Text(
                    L.t(lang, 'noAlertsTitle'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    L.t(lang, 'noAlertsBody'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 19, color: AgriColors.inkSoft),
                  ),
                ],
              ),
            )
          else
            ...alerts.map(
              (alert) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AgriColors.levelSoft(alert.level),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: AgriColors.level(alert.level), width: 2),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.warning_rounded,
                          color: AgriColors.level(alert.level), size: 38),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              alert.title,
                              style: TextStyle(
                                fontSize: 21,
                                fontWeight: FontWeight.w900,
                                color: AgriColors.level(alert.level),
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(alert.message,
                                style: const TextStyle(fontSize: 19, height: 1.3)),
                            const SizedBox(height: 6),
                            SpeakerButton(
                              text: '${alert.title}. ${alert.message}',
                              language: lang,
                              compact: true,
                              color: AgriColors.level(alert.level),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Row(
                    children: [
                      const Icon(Icons.cloud_off_rounded,
                          color: AgriColors.warning, size: 30),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(_error!, style: const TextStyle(fontSize: 18)),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          const SizedBox(height: 12),
          FilledButton.tonal(
            onPressed: () => context.go('/weather'),
            child: Text(L.t(lang, 'weatherTitle')),
          ),
        ],
      ),
    );
  }
}
