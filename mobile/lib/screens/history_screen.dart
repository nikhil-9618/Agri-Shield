import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/strings.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../providers.dart';
import '../widgets/common.dart';

class HistoryScreen extends ConsumerStatefulWidget {
  const HistoryScreen({super.key});

  @override
  ConsumerState<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends ConsumerState<HistoryScreen> {
  bool _syncing = false;

  Future<void> _sync() async {
    if (_syncing) return;
    setState(() => _syncing = true);
    final lang = ref.read(appProvider).language;
    final count = await ref.read(appProvider.notifier).syncQueue();
    if (!mounted) return;
    setState(() => _syncing = false);
    showBigSnack(
      context,
      count > 0
          ? L.t(lang, 'syncedCount', vars: {'count': '$count'})
          : L.t(lang, 'serverOffline'),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(appProvider);
    final lang = state.language;
    final saved = state.saved;

    return Scaffold(
      appBar: AppBar(
        title: Text(L.t(lang, 'historyTitle')),
        actions: [
          SpeakerButton(
            text: L.t(lang, 'historyTitle'),
            language: lang,
            color: Colors.white,
          ),
          const SizedBox(width: 6),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (state.queue.isNotEmpty)
            OfflineBanner(
              pending: state.queue.length,
              language: lang,
              onSync: _sync,
              syncing: _syncing,
            ),
          if (saved.isEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 50),
              child: Column(
                children: [
                  const Icon(Icons.eco_rounded, size: 100, color: AgriColors.secondary),
                  const SizedBox(height: 14),
                  Text(
                    L.t(lang, 'historyEmptyTitle'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    L.t(lang, 'historyEmptyBody'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 19, color: AgriColors.inkSoft),
                  ),
                  const SizedBox(height: 20),
                  FilledButton.icon(
                    onPressed: () => context.push('/camera'),
                    icon: const Icon(Icons.photo_camera_rounded),
                    label: Text(L.t(lang, 'checkCrop')),
                  ),
                ],
              ),
            )
          else
            ...saved.map((d) => _HistoryTile(diagnosis: d, language: lang)),
          const SizedBox(height: 18),
          OutlinedButton.icon(
            onPressed: () => context.push('/camera'),
            icon: const Icon(Icons.add_a_photo_rounded, size: 26),
            label: Text(L.t(lang, 'newCheck')),
          ),
        ],
      ),
    );
  }
}

class _HistoryTile extends StatelessWidget {
  final Diagnosis diagnosis;
  final String language;

  const _HistoryTile({required this.diagnosis, required this.language});

  @override
  Widget build(BuildContext context) {
    final color = AgriColors.level(diagnosis.level);
    final name = diagnosis.advisory.name.isNotEmpty
        ? diagnosis.advisory.name
        : diagnosis.diseaseName;
    final date = diagnosis.createdAt.toLocal();
    final stamp =
        '${date.day}/${date.month}/${date.year} ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Card(
        child: InkWell(
          borderRadius: BorderRadius.circular(22),
          onTap: () => context.push('/result', extra: diagnosis),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              children: [
                Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    color: AgriColors.levelSoft(diagnosis.level),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Icon(
                    diagnosis.level == 'green'
                        ? Icons.verified_rounded
                        : diagnosis.level == 'red'
                            ? Icons.warning_rounded
                            : Icons.help_rounded,
                    color: color,
                    size: 38,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        name.isEmpty ? L.t(language, 'resultTitle') : name,
                        style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        '${diagnosis.cropName} • ${(diagnosis.confidence * 100).round()}%',
                        style: const TextStyle(fontSize: 16, color: AgriColors.inkSoft),
                      ),
                      Text(
                        stamp,
                        style: const TextStyle(fontSize: 14, color: AgriColors.inkSoft),
                      ),
                      if (diagnosis.status == 'unclear')
                        Text(
                          L.t(language, 'levelWarning'),
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            color: AgriColors.warning,
                          ),
                        ),
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right_rounded, size: 32, color: AgriColors.inkSoft),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
