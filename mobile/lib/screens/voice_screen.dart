import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/api_client.dart';
import '../core/strings.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../providers.dart';
import '../widgets/common.dart';

class VoiceScreen extends ConsumerStatefulWidget {
  const VoiceScreen({super.key});

  @override
  ConsumerState<VoiceScreen> createState() => _VoiceScreenState();
}

class _VoiceScreenState extends ConsumerState<VoiceScreen> {
  bool _listening = false;
  bool _loading = false;
  String? _transcript;
  String? _error;
  AssistantAnswer? _answer;

  static const Map<String, List<String>> _suggestions = {
    'te': [
      'నా ఆకు పసుపు రంగులో ఉంది, ఏం చేయాలి?',
      'టమాటా ఆకుపై నల్ల మచ్చలు ఉన్నాయి',
      'రేపు వర్షం పడుతుందా?',
      'పురుగుమందు ఎప్పుడు వేయాలి?',
    ],
    'hi': [
      'मेरी पत्ती पीली हो रही है, क्या करें?',
      'टमाटर पर काले धब्बे हैं',
      'कल बारिश होगी?',
      'कीटनाशक कब डालें?',
    ],
    'en': [
      'My leaves are turning yellow, what should I do?',
      'What are the black spots on my tomato leaves?',
      'Will it rain tomorrow?',
      'When should I spray my crop?',
    ],
    'ta': [
      'என் இலை மஞ்சளாகிறது, என்ன செய்ய வேண்டும்?',
      'தக்காளி இலையில் கருப்பு புள்ளிகள் உள்ளன',
      'நாளை மழை பெய்யுமா?',
      'பூச்சிக்கொல்லி எப்போது தெளிக்க வேண்டும்?',
    ],
    'kn': [
      'ನನ್ನ ಎಲೆ ಹಳದಿ ಆಗುತ್ತಿದೆ, ಏನು ಮಾಡಬೇಕು?',
      'ಟೊಮ್ಯಾಟೊ ಎಲೆಯಲ್ಲಿ ಕಪ್ಪು ಚುಕ್ಕೆಗಳಿವೆ',
      'ನಾಳೆ ಮಳೆ ಬರುತ್ತದೆಯೇ?',
      'ಕೀಟನಾಶಕ ಯಾವಾಗ ಸಿಂಪಡಿಸಬೇಕು?',
    ],
  };

  Future<void> _toggleMic() async {
    if (_listening) {
      await ref.read(speechProvider).stopListening();
      if (mounted) setState(() => _listening = false);
      return;
    }
    final lang = ref.read(appProvider).language;
    setState(() {
      _error = null;
      _answer = null;
      _transcript = null;
    });
    final started = await ref.read(speechProvider).listen(
          language: lang,
          onResult: (text, isFinal) {
            if (!mounted) return;
            setState(() {
              _transcript = text;
              _listening = !isFinal;
            });
            if (isFinal && text.trim().isNotEmpty) {
              _ask(text.trim());
            }
          },
          onError: (error) {
            if (!mounted) return;
            setState(() {
              _listening = false;
              _error = error.contains('permission')
                  ? L.t(lang, 'micDenied')
                  : L.t(lang, 'speechNotAvailable');
            });
          },
        );
    if (!started) {
      setState(() {
        _error = L.t(lang, 'speechNotAvailable');
        _listening = false;
      });
    } else {
      setState(() => _listening = true);
    }
  }

  Future<void> _ask(String question) async {
    if (question.trim().isEmpty) return;
    final lang = ref.read(appProvider).language;
    setState(() {
      _loading = true;
      _transcript = question;
      _error = null;
    });
    await ref.read(speechProvider).stopListening();
    try {
      final answer = await ref.read(apiProvider).ask(question, lang);
      if (!mounted) return;
      setState(() {
        _answer = answer;
        _loading = false;
      });
      await ref.read(speechProvider).speak(answer.answer, lang);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = e.status == 0 ? L.t(lang, 'serverOffline') : L.t(lang, 'commonError');
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
    final suggestions = _suggestions[lang] ?? _suggestions['en']!;
    final answer = _answer;

    return Scaffold(
      appBar: AppBar(
        title: Text(L.t(lang, 'voiceTitle')),
        actions: [
          SpeakerButton(
            text: L.t(lang, 'voiceIntro'),
            language: lang,
            color: Colors.white,
          ),
          const SizedBox(width: 6),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(18, 16, 18, 26),
        children: [
          Text(
            L.t(lang, 'voiceIntro'),
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 21, color: AgriColors.inkSoft),
          ),
          const SizedBox(height: 18),
          Center(
            child: Semantics(
              button: true,
              label: _listening ? L.t(lang, 'listeningNow') : L.t(lang, 'tapToSpeak'),
              child: GestureDetector(
                onTap: _toggleMic,
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 220),
                  width: 168,
                  height: 168,
                  decoration: BoxDecoration(
                    color: _listening ? AgriColors.urgent : AgriColors.primary,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: (_listening ? AgriColors.urgent : AgriColors.primary)
                            .withValues(alpha: 0.35),
                        blurRadius: _listening ? 34 : 14,
                        spreadRadius: _listening ? 10 : 2,
                      ),
                    ],
                  ),
                  child: Icon(
                    _listening ? Icons.graphic_eq_rounded : Icons.mic_rounded,
                    size: 86,
                    color: Colors.white,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Text(
            _listening
                ? L.t(lang, 'listeningNow')
                : _transcript == null
                    ? L.t(lang, 'tapToSpeak')
                    : L.t(lang, 'askAgain'),
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
          ),
          if (_transcript != null && _transcript!.isNotEmpty) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: const Color(0xFFE7E3D5)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.person_rounded, color: AgriColors.inkSoft, size: 28),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _transcript!,
                      style: const TextStyle(fontSize: 20),
                    ),
                  ),
                ],
              ),
            ),
          ],
          if (_loading) ...[
            const SizedBox(height: 24),
            const Center(child: CircularProgressIndicator(strokeWidth: 6)),
            const SizedBox(height: 8),
            Text(
              L.t(lang, 'thinking'),
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 19, color: AgriColors.inkSoft),
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AgriColors.warningSoft,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.cloud_off_rounded,
                          color: AgriColors.warning, size: 30),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(_error!, style: const TextStyle(fontSize: 18)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  FilledButton.tonalIcon(
                    onPressed: () => context.push('/server'),
                    icon: const Icon(Icons.dns_rounded),
                    label: Text(L.t(lang, 'serverSetupAction')),
                  ),
                ],
              ),
            ),
          ],
          if (answer != null) ...[
            const SizedBox(height: 20),
            Card(
              color: AgriColors.secondarySoft,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.assistant_rounded,
                            color: AgriColors.primary, size: 32),
                        const SizedBox(width: 8),
                        Text(
                          L.t(lang, 'answerTitle'),
                          style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w800),
                        ),
                        const Spacer(),
                        SpeakerButton(text: answer.answer, language: lang, compact: true),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(answer.answer,
                        style: const TextStyle(fontSize: 20, height: 1.35)),
                    if (answer.sources.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: answer.sources
                            .map(
                              (s) => Chip(
                                avatar: const Icon(Icons.menu_book_rounded, size: 20),
                                label: Text(s),
                              ),
                            )
                            .toList(),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            if (answer.followUps.isNotEmpty) ...[
              const SizedBox(height: 14),
              Text(
                L.t(lang, 'tryAsking'),
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: answer.followUps
                    .map(
                      (q) => ActionChip(
                        label: Text(q),
                        onPressed: () => _ask(q),
                      ),
                    )
                    .toList(),
              ),
            ],
          ],
          if (answer == null && !_loading) ...[
            const SizedBox(height: 22),
            Text(
              L.t(lang, 'tryAsking'),
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 10),
            ...suggestions.map(
              (q) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: OutlinedButton(
                  onPressed: () => _ask(q),
                  style: OutlinedButton.styleFrom(
                    minimumSize: const Size.fromHeight(64),
                    alignment: Alignment.centerLeft,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.chat_bubble_outline_rounded, size: 26),
                      const SizedBox(width: 10),
                      Expanded(child: Text(q, style: const TextStyle(fontSize: 18))),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
