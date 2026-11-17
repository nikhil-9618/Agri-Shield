import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/strings.dart';
import '../core/theme.dart';
import '../providers.dart';
import '../widgets/common.dart';

class WelcomeScreen extends ConsumerWidget {
  const WelcomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lang = ref.watch(appProvider.select((s) => s.language));
    final notifier = ref.read(appProvider.notifier);

    final steps = [
      (Icons.photo_camera_rounded, L.t(lang, 'howTo1Title'), L.t(lang, 'howTo1Body')),
      (Icons.traffic_rounded, L.t(lang, 'howTo2Title'), L.t(lang, 'howTo2Body')),
      (Icons.hearing_rounded, L.t(lang, 'howTo3Title'), L.t(lang, 'howTo3Body')),
    ];

    final spoken = [
      L.t(lang, 'welcomeTitle'),
      L.t(lang, 'welcomeBody'),
      ...steps.map((s) => '${s.$2}. ${s.$3}'),
    ].join(' ');

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 24, 20, 8),
                children: [
                  Center(
                    child: Container(
                      width: 132,
                      height: 132,
                      decoration: BoxDecoration(
                        color: AgriColors.secondarySoft,
                        borderRadius: BorderRadius.circular(66),
                        border: Border.all(color: AgriColors.secondary, width: 4),
                      ),
                      child: Image.asset(
                        'assets/branding/logo.png',
                        width: 112,
                        height: 112,
                        filterQuality: FilterQuality.high,
                        semanticLabel: 'AgriShield',
                      ),
                    ),
                  ),
                  const SizedBox(height: 18),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Flexible(
                        child: Text(
                          L.t(lang, 'welcomeTitle'),
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            fontSize: 32,
                            fontWeight: FontWeight.w900,
                            color: AgriColors.primary,
                          ),
                        ),
                      ),
                      SpeakerButton(text: spoken, language: lang),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    L.t(lang, 'welcomeBody'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 21, color: AgriColors.inkSoft),
                  ),
                  const SizedBox(height: 18),
                  ...steps.map(
                    (step) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Card(
                        child: Padding(
                          padding: const EdgeInsets.all(14),
                          child: Row(
                            children: [
                              Container(
                                width: 72,
                                height: 72,
                                decoration: BoxDecoration(
                                  color: AgriColors.primary.withValues(alpha: 0.10),
                                  borderRadius: BorderRadius.circular(18),
                                ),
                                child: Icon(step.$1, size: 44, color: AgriColors.primary),
                              ),
                              const SizedBox(width: 14),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      step.$2,
                                      style: const TextStyle(
                                        fontSize: 21,
                                        fontWeight: FontWeight.w800,
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      step.$3,
                                      style: const TextStyle(
                                        fontSize: 18,
                                        color: AgriColors.inkSoft,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(18, 4, 18, 18),
              child: FilledButton(
                onPressed: () async {
                  await notifier.markOnboarded();
                  await ref.read(speechProvider).stop();
                  if (context.mounted) context.go('/home');
                },
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.play_arrow_rounded, size: 34),
                    const SizedBox(width: 8),
                    Text(L.t(lang, 'startNow')),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
