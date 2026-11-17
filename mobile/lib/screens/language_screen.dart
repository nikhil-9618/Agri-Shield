import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/strings.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../providers.dart';

class LanguageScreen extends ConsumerWidget {
  const LanguageScreen({super.key});

  static const Map<String, String> _marks = {
    'te': 'తె',
    'hi': 'हि',
    'en': 'A',
    'ta': 'த',
    'kn': 'ಕ',
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selected = ref.watch(appProvider.select((s) => s.settings.language));
    final speech = ref.read(speechProvider);

    Future<void> choose(String lang) async {
      await ref.read(appProvider.notifier).setLanguage(lang);
      await speech.speak(L.languageSample[lang] ?? '', lang);
    }

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 26, 20, 8),
              child: Row(
                children: [
                  const Icon(Icons.agriculture_rounded, size: 52, color: AgriColors.primary),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      L.t(selected, 'appName'),
                      style: const TextStyle(
                        fontSize: 30,
                        fontWeight: FontWeight.w900,
                        color: AgriColors.primary,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Column(
                children: [
                  Text(
                    L.t(selected, 'chooseLanguageQ'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 27, fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    L.t(selected, 'chooseLanguageHint'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 18, color: AgriColors.inkSoft),
                  ),
                ],
              ),
            ),
            Expanded(
              child: ListView.separated(
                padding: const EdgeInsets.all(18),
                itemCount: kLanguages.length,
                separatorBuilder: (_, _) => const SizedBox(height: 12),
                itemBuilder: (context, i) {
                  final lang = kLanguages[i];
                  final active = lang == selected;
                  return Semantics(
                    button: true,
                    selected: active,
                    label: L.languageNames[lang],
                    child: Card(
                      color: active ? AgriColors.secondarySoft : Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(22),
                        side: BorderSide(
                          color: active ? AgriColors.primary : const Color(0xFFE7E3D5),
                          width: active ? 3 : 1,
                        ),
                      ),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(22),
                        onTap: () => choose(lang),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                          child: Row(
                            children: [
                              Container(
                                width: 62,
                                height: 62,
                                alignment: Alignment.center,
                                decoration: BoxDecoration(
                                  color: AgriColors.primary.withValues(alpha: 0.10),
                                  borderRadius: BorderRadius.circular(50),
                                ),
                                child: Text(
                                  _marks[lang]!,
                                  style: const TextStyle(
                                    fontSize: 30,
                                    fontWeight: FontWeight.w900,
                                    color: AgriColors.primary,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 16),
                              Expanded(
                                child: Text(
                                  L.languageNames[lang]!,
                                  style: const TextStyle(
                                    fontSize: 26,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                              ),
                              IconButton(
                                tooltip: L.t(lang, 'listenExplain'),
                                iconSize: 30,
                                onPressed: () =>
                                    speech.speak(L.languageSample[lang] ?? '', lang),
                                icon: const Icon(
                                  Icons.volume_up_rounded,
                                  color: AgriColors.primary,
                                ),
                              ),
                              if (active)
                                const Icon(
                                  Icons.check_circle_rounded,
                                  color: AgriColors.primary,
                                  size: 32,
                                ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(18, 0, 18, 18),
              child: FilledButton(
                onPressed: () => context.go('/welcome'),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.arrow_forward_rounded, size: 30),
                    const SizedBox(width: 10),
                    Text(L.t(selected, 'continueBig')),
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
