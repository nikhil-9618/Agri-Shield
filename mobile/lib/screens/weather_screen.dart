import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/strings.dart';
import '../core/theme.dart';
import '../core/weather_loader.dart';
import '../models/models.dart';
import '../providers.dart';
import '../widgets/common.dart';

class WeatherScreen extends ConsumerStatefulWidget {
  const WeatherScreen({super.key});

  @override
  ConsumerState<WeatherScreen> createState() => _WeatherScreenState();
}

class _WeatherScreenState extends ConsumerState<WeatherScreen> {
  WeatherSnapshot? _snapshot;
  bool _loading = false;
  bool _stale = false;
  String? _error;
  bool _locationProblem = false;

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
      _locationProblem = false;
    });
    final lang = ref.read(appProvider).language;
    try {
      final snapshot = await loadWeatherForDevice(ref.read(apiProvider), lang);
      await ref.read(appProvider.notifier).cacheWeather(snapshot);
      if (!mounted) return;
      setState(() {
        _snapshot = snapshot;
        _stale = false;
        _loading = false;
      });
    } on LocationUnavailable {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _locationProblem = true;
        _error = L.t(lang, 'needLocation');
      });
    } on WeatherUnavailable catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _stale = _snapshot != null;
        _error = e.message == 'offline'
            ? L.t(lang, 'weatherOffline')
            : L.t(lang, 'commonError');
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _stale = _snapshot != null;
        _error = L.t(lang, 'commonError');
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final lang = ref.watch(appProvider.select((s) => s.language));
    final snapshot = _snapshot;

    return Scaffold(
      appBar: AppBar(
        title: Text(L.t(lang, 'weatherTitle')),
        actions: [
          IconButton(
            onPressed: _load,
            iconSize: 30,
            tooltip: L.t(lang, 'refresh'),
            icon: _loading
                ? const SizedBox(
                    width: 26,
                    height: 26,
                    child: CircularProgressIndicator(color: Colors.white, strokeWidth: 3),
                  )
                : const Icon(Icons.refresh_rounded),
          ),
          const SizedBox(width: 6),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
          children: [
            if (snapshot != null) ...[
              _WeatherHeader(snapshot: snapshot, language: lang),
              const SizedBox(height: 14),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  InfoChip(
                    icon: Icons.thermostat_rounded,
                    label: L.t(lang, 'tempLabel'),
                    value: snapshot.temperature == null
                        ? '--'
                        : '${snapshot.temperature!.round()}°C',
                    color: AgriColors.urgent,
                  ),
                  InfoChip(
                    icon: Icons.water_drop_rounded,
                    label: L.t(lang, 'humidityLabel'),
                    value: snapshot.humidity == null ? '--' : '${snapshot.humidity}%',
                    color: const Color(0xFF1565C0),
                  ),
                  InfoChip(
                    icon: Icons.umbrella_rounded,
                    label: L.t(lang, 'rainLabel'),
                    value: snapshot.rainfall == null
                        ? '--'
                        : '${snapshot.rainfall!.toStringAsFixed(1)} mm',
                    color: AgriColors.primary,
                  ),
                  InfoChip(
                    icon: Icons.air_rounded,
                    label: L.t(lang, 'windLabel'),
                    value: snapshot.wind == null ? '--' : '${snapshot.wind!.round()} km/h',
                    color: AgriColors.inkSoft,
                  ),
                ],
              ),
              if (snapshot.rainTomorrow != null) ...[
                const SizedBox(height: 10),
                InfoChip(
                  icon: Icons.water_rounded,
                  label: L.t(lang, 'rainTomorrowLabel'),
                  value: '${snapshot.rainTomorrow}%',
                  color: const Color(0xFF1565C0),
                ),
              ],
              if (_stale)
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: Text(
                    '${L.t(lang, 'weatherUpdated')}: ${_time(snapshot.fetchedAt)}',
                    style: const TextStyle(fontSize: 16, color: AgriColors.inkSoft),
                  ),
                ),
              const SizedBox(height: 20),
              Text(
                L.t(lang, 'warningTitle'),
                style: const TextStyle(fontSize: 23, fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 10),
              if (snapshot.alerts.isEmpty)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      children: [
                        const Icon(Icons.check_circle_rounded,
                            color: AgriColors.healthy, size: 36),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            L.t(lang, 'noAlertsBody'),
                            style: const TextStyle(fontSize: 18),
                          ),
                        ),
                      ],
                    ),
                  ),
                )
              else
                ...snapshot.alerts.map((alert) => _AlertCard(alert: alert)),
              if (snapshot.advice.isNotEmpty) ...[
                const SizedBox(height: 18),
                Text(
                  L.t(lang, 'cropRiskTitle'),
                  style: const TextStyle(fontSize: 23, fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 10),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: snapshot.advice
                          .map(
                            (line) => Padding(
                              padding: const EdgeInsets.only(bottom: 10),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Icon(Icons.eco_rounded,
                                      color: AgriColors.primary, size: 26),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(line,
                                        style: const TextStyle(fontSize: 18, height: 1.3)),
                                  ),
                                ],
                              ),
                            ),
                          )
                          .toList(),
                    ),
                  ),
                ),
              ],
              if (snapshot.days.isNotEmpty) ...[
                const SizedBox(height: 20),
                Text(
                  L.t(lang, 'sevenDayTitle'),
                  style: const TextStyle(fontSize: 23, fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 10),
                Card(
                  child: Column(
                    children: snapshot.days.asMap().entries.map((entry) {
                      final day = entry.value;
                      return ListTile(
                        leading: const Icon(Icons.calendar_month_rounded,
                            color: AgriColors.primary, size: 30),
                        title: Text(
                          _dayLabel(day.date, entry.key, lang),
                          style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w700),
                        ),
                        subtitle: Text(
                          '${day.min?.round() ?? '--'}° / ${day.max?.round() ?? '--'}°',
                          style: const TextStyle(fontSize: 17),
                        ),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.water_drop_rounded,
                                color: Color(0xFF1565C0), size: 22),
                            const SizedBox(width: 4),
                            Text(
                              '${day.rainChance ?? 0}%',
                              style: const TextStyle(
                                  fontSize: 18, fontWeight: FontWeight.w700),
                            ),
                          ],
                        ),
                      );
                    }).toList(),
                  ),
                ),
              ],
            ],
            if (_error != null) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AgriColors.warningSoft,
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: AgriColors.warning),
                ),
                child: Column(
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.location_off_rounded,
                            color: AgriColors.warning, size: 32),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(_error!, style: const TextStyle(fontSize: 18)),
                        ),
                      ],
                    ),
                    if (_locationProblem)
                      Padding(
                        padding: const EdgeInsets.only(top: 10),
                        child: FilledButton.tonalIcon(
                          onPressed: _load,
                          icon: const Icon(Icons.my_location_rounded),
                          label: Text(L.t(lang, 'allowLocation')),
                        ),
                      ),
                  ],
                ),
              ),
            ],
            if (snapshot == null && _loading)
              const Padding(
                padding: EdgeInsets.only(top: 80),
                child: Center(
                  child: Column(
                    children: [
                      CircularProgressIndicator(strokeWidth: 6),
                      SizedBox(height: 16),
                      Text('...', style: TextStyle(fontSize: 20)),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  String _time(DateTime date) {
    final local = date.toLocal();
    final h = local.hour.toString().padLeft(2, '0');
    final m = local.minute.toString().padLeft(2, '0');
    return '${local.day}/${local.month} $h:$m';
  }

  String _dayLabel(String iso, int index, String lang) {
    final parsed = DateTime.tryParse(iso);
    if (parsed == null) return iso;
    final date = '${parsed.day}/${parsed.month}';
    if (index == 0) return '${L.t(lang, 'navHome')} • $date';
    return date;
  }
}

class _WeatherHeader extends StatelessWidget {
  final WeatherSnapshot snapshot;
  final String language;
  const _WeatherHeader({required this.snapshot, required this.language});

  @override
  Widget build(BuildContext context) {
    final temp = snapshot.temperature;
    final isRainy = snapshot.condition.toLowerCase().contains('rain');
    final icon = isRainy
        ? Icons.grain_rounded
        : (temp != null && temp > 34)
            ? Icons.wb_sunny_rounded
            : Icons.wb_cloudy_rounded;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF1565C0), Color(0xFF42A5F5)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(26),
      ),
      child: Row(
        children: [
          Icon(icon, size: 90, color: Colors.white),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  temp == null ? '--' : '${temp.round()}°C',
                  style: const TextStyle(
                    fontSize: 48,
                    fontWeight: FontWeight.w900,
                    color: Colors.white,
                    height: 1,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  snapshot.condition.isEmpty ? L.t(language, 'weatherTitle') : snapshot.condition,
                  style: const TextStyle(fontSize: 22, color: Colors.white),
                ),
              ],
            ),
          ),
          SpeakerButton(
            text:
                '${snapshot.condition}. ${L.t(language, 'tempLabel')} ${temp?.round() ?? ''}. ${L.t(language, 'humidityLabel')} ${snapshot.humidity ?? ''}. ${snapshot.advice.join('. ')}',
            language: language,
            color: Colors.white,
          ),
        ],
      ),
    );
  }
}

class _AlertCard extends StatelessWidget {
  final WeatherAlert alert;
  const _AlertCard({required this.alert});

  @override
  Widget build(BuildContext context) {
    final color = AgriColors.level(alert.level);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AgriColors.levelSoft(alert.level),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: color, width: 2),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.warning_rounded, color: color, size: 34),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    alert.title,
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                      color: color,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(alert.message, style: const TextStyle(fontSize: 18, height: 1.3)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
