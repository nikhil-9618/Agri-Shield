import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/strings.dart';
import '../core/theme.dart';
import '../providers.dart';
import '../widgets/common.dart';

class HelpScreen extends ConsumerWidget {
  const HelpScreen({super.key});

  static const String _helpline = '18001801551';

  Future<void> _call(BuildContext context, String lang) async {
    final ok = await launchUrl(Uri.parse('tel:$_helpline'));
    if (!ok && context.mounted) {
      showBigSnack(context, L.t(lang, 'helpHelpline'));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lang = ref.watch(appProvider.select((s) => s.language));
    final steps = [
      (Icons.photo_camera_rounded, L.t(lang, 'howTo1Title'), L.t(lang, 'howTo1Body')),
      (Icons.traffic_rounded, L.t(lang, 'howTo2Title'), L.t(lang, 'howTo2Body')),
      (Icons.hearing_rounded, L.t(lang, 'howTo3Title'), L.t(lang, 'howTo3Body')),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text(L.t(lang, 'helpTitle')),
        actions: [
          SpeakerButton(
            text: '${L.t(lang, 'helpCallOfficer')}. ${L.t(lang, 'helpHelpline')}.',
            language: lang,
            color: Colors.white,
          ),
          const SizedBox(width: 6),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            color: AgriColors.urgentSoft,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.support_agent_rounded,
                          color: AgriColors.urgent, size: 42),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          L.t(lang, 'helpCallOfficer'),
                          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    L.t(lang, 'helpHelpline'),
                    style: const TextStyle(fontSize: 19),
                  ),
                  const SizedBox(height: 12),
                  FilledButton.icon(
                    onPressed: () => _call(context, lang),
                    icon: const Icon(Icons.call_rounded, size: 30),
                    label: Text(L.t(lang, 'helpCallOfficer')),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 14),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  const Icon(Icons.local_library_rounded,
                      color: AgriColors.primary, size: 40),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          L.t(lang, 'helpKVK'),
                          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
                        ),
                        const SizedBox(height: 2),
                        const Text(
                          'Your district Krishi Vigyan Kendra can visit your field.',
                          style: TextStyle(fontSize: 16, color: AgriColors.inkSoft),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    onPressed: () => _call(context, lang),
                    iconSize: 30,
                    icon: const Icon(Icons.call_rounded, color: AgriColors.primary),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 22),
          Text(
            L.t(lang, 'helpHowTo'),
            style: const TextStyle(fontSize: 23, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 10),
          ...steps.map(
            (step) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Row(
                    children: [
                      Icon(step.$1, size: 38, color: AgriColors.primary),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(step.$2,
                                style: const TextStyle(
                                    fontSize: 19, fontWeight: FontWeight.w800)),
                            const SizedBox(height: 2),
                            Text(step.$3,
                                style: const TextStyle(
                                    fontSize: 17, color: AgriColors.inkSoft)),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.lock_rounded, color: AgriColors.healthy, size: 32),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      L.t(lang, 'helpPrivacy'),
                      style: const TextStyle(fontSize: 18, height: 1.3),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => context.push('/profile'),
                  icon: const Icon(Icons.person_rounded),
                  label: Text(L.t(lang, 'profileTitle')),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => context.go('/welcome'),
                  icon: const Icon(Icons.slideshow_rounded),
                  label: Text(L.t(lang, 'startNow')),
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          Center(
            child: Text(
              '${L.t(lang, 'helpVersion')} 1.0.0',
              style: const TextStyle(fontSize: 15, color: AgriColors.inkSoft),
            ),
          ),
        ],
      ),
    );
  }
}
