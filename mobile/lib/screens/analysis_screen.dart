import 'dart:async';
import 'dart:io';

import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/api_client.dart';
import '../core/strings.dart';
import '../core/theme.dart';
import '../providers.dart';
import '../widgets/agrishield_logo.dart';
import '../widgets/common.dart';

class AnalysisScreen extends ConsumerStatefulWidget {
  final String imagePath;
  const AnalysisScreen({super.key, required this.imagePath});

  @override
  ConsumerState<AnalysisScreen> createState() => _AnalysisScreenState();
}

class _AnalysisScreenState extends ConsumerState<AnalysisScreen> {
  int _stage = 0;
  bool _queued = false;
  String? _error;
  String? _rejection;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    Future.microtask(_run);
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _run() async {
    _timer?.cancel();
    setState(() {
      _stage = 0;
      _error = null;
      _rejection = null;
      _queued = false;
    });
    final lang = ref.read(appProvider).language;
    final file = File(widget.imagePath);
    if (!file.existsSync()) {
      setState(() => _error = L.t(lang, 'commonError'));
      return;
    }

    _timer = Timer.periodic(const Duration(milliseconds: 1400), (_) {
      if (!mounted) return;
      setState(() => _stage = _stage < 2 ? _stage + 1 : _stage);
    });

    try {
      final diagnosis =
          await ref.read(appProvider.notifier).diagnose(image: file, language: lang);
      _timer?.cancel();
      if (!mounted) return;
      if (diagnosis == null) {
        setState(() => _queued = true);
        return;
      }
      context.pushReplacement('/result', extra: diagnosis);
    } on ApiException catch (e) {
      _timer?.cancel();
      if (!mounted) return;
      if (e.code == 'not_a_leaf') {
        setState(() => _rejection = e.message);
        return;
      }
      final friendly = switch (e.code) {
        'invalid_image' => L.t(lang, 'commonError'),
        'leaf_check_unavailable' => L.t(lang, 'leafCheckUnavailable'),
        'model_unavailable' => e.message,
        _ => e.status == 0 ? L.t(lang, 'serverOffline') : e.message,
      };
      setState(() => _error = friendly);
    } catch (_) {
      _timer?.cancel();
      if (!mounted) return;
      setState(() => _error = L.t(lang, 'commonError'));
    }
  }

  @override
  Widget build(BuildContext context) {
    final lang = ref.watch(appProvider.select((s) => s.language));
    final steps = [
      L.t(lang, 'stepLeaf'),
      L.t(lang, 'stepChecking'),
      L.t(lang, 'stepExplaining'),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text(L.t(lang, 'analysisTitle')),
        automaticallyImplyLeading: false,
      ),
      body: SafeArea(
        child: _rejection != null
            ? _NotLeafView(
                imagePath: widget.imagePath,
                reason: _rejection!,
                language: lang,
              )
            : _queued
                ? _QueuedView(imagePath: widget.imagePath)
                : _error != null
                ? Center(
                    child: ErrorView(
                      message: _error!,
                      language: lang,
                      onRetry: _run,
                    ),
                  )
                : ListView(
                    padding: const EdgeInsets.all(20),
                    children: [
                      ClipRRect(
                        borderRadius: BorderRadius.circular(24),
                        child: Image.file(
                          File(widget.imagePath),
                          height: 240,
                          width: double.infinity,
                          fit: BoxFit.cover,
                          errorBuilder: (_, _, _) => Container(
                            height: 240,
                            color: AgriColors.secondarySoft,
                            child: const Icon(Icons.eco_rounded,
                                size: 110, color: AgriColors.primary),
                          ),
                        ),
                      ),
                      const SizedBox(height: 22),
                      const Center(
                        child: AgriShieldLogo(width: 86, height: 86),
                      ),
                      const SizedBox(height: 18),
                      const Center(
                        child: SizedBox(
                          width: 84,
                          height: 84,
                          child: CircularProgressIndicator(strokeWidth: 8),
                        ),
                      ),
                      const SizedBox(height: 22),
                      Text(
                        L.t(lang, 'analysisWait'),
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontSize: 25, fontWeight: FontWeight.w800),
                      ),
                      const SizedBox(height: 22),
                      ...steps.asMap().entries.map(
                            (entry) => Padding(
                              padding: const EdgeInsets.only(bottom: 12),
                              child: Row(
                                children: [
                                  Icon(
                                    entry.key <= _stage
                                        ? Icons.check_circle_rounded
                                        : Icons.radio_button_unchecked_rounded,
                                    size: 34,
                                    color: entry.key <= _stage
                                        ? AgriColors.healthy
                                        : const Color(0xFFBDBDBD),
                                  ),
                                  const SizedBox(width: 12),
                                  Expanded(
                                    child: Text(
                                      entry.value,
                                      style: TextStyle(
                                        fontSize: 21,
                                        fontWeight: entry.key == _stage
                                            ? FontWeight.w800
                                            : FontWeight.w500,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                      const SizedBox(height: 10),
                      Text(
                        L.t(lang, 'analysisTitle'),
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontSize: 17, color: AgriColors.inkSoft),
                      ),
                    ],
                  ),
      ),
    );
  }
}

class _NotLeafView extends StatelessWidget {
  final String imagePath;
  final String reason;
  final String language;

  const _NotLeafView({
    required this.imagePath,
    required this.reason,
    required this.language,
  });

  @override
  Widget build(BuildContext context) {
    final body = reason == 'person'
        ? L.t(language, 'notLeafPerson')
        : L.t(language, 'notLeafNoLeaf');

    return ListView(
      padding: const EdgeInsets.all(22),
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(24),
          child: Image.file(
            File(imagePath),
            height: 220,
            width: double.infinity,
            fit: BoxFit.cover,
            errorBuilder: (_, _, _) => Container(
              height: 220,
              color: AgriColors.secondarySoft,
              child: const Icon(Icons.eco_rounded, size: 100, color: AgriColors.primary),
            ),
          ),
        ),
        const SizedBox(height: 22),
        Center(
          child: Container(
            width: 92,
            height: 92,
            decoration: BoxDecoration(
              color: AgriColors.warning.withValues(alpha: 0.16),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.search_off_rounded, size: 52, color: AgriColors.warning),
          ),
        ),
        const SizedBox(height: 16),
        Text(
          L.t(language, 'notLeafTitle'),
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 27, fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 12),
        Text(
          body,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 21, height: 1.35),
        ),
        const SizedBox(height: 18),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AgriColors.secondarySoft,
            borderRadius: BorderRadius.circular(18),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.lightbulb_rounded, color: AgriColors.primary, size: 30),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  L.t(language, 'notLeafHint'),
                  style: const TextStyle(fontSize: 19, height: 1.3),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        FilledButton.icon(
          onPressed: () => context.pushReplacement('/camera'),
          icon: const Icon(Icons.photo_camera_rounded, size: 28),
          label: Text(L.t(language, 'notLeafRetry')),
        ),
        const SizedBox(height: 10),
        OutlinedButton(
          onPressed: () => context.go('/home'),
          child: Text(L.t(language, 'navHome')),
        ),
      ],
    );
  }
}

class _QueuedView extends ConsumerWidget {
  final String imagePath;
  const _QueuedView({required this.imagePath});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lang = ref.watch(appProvider.select((s) => s.language));
    return ListView(
      padding: const EdgeInsets.all(22),
      children: [
        const SizedBox(height: 24),
        const Center(
          child: Icon(Icons.cloud_off_rounded, size: 110, color: AgriColors.warning),
        ),
        const SizedBox(height: 18),
        Text(
          L.t(lang, 'queuedTitle'),
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 12),
        Text(
          L.t(lang, 'queuedBody'),
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 21, height: 1.35),
        ),
        const SizedBox(height: 24),
        ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: Image.file(
            File(imagePath),
            height: 170,
            width: double.infinity,
            fit: BoxFit.cover,
            errorBuilder: (_, _, _) => const SizedBox.shrink(),
          ),
        ),
        const SizedBox(height: 26),
        FilledButton(
          onPressed: () => context.go('/home'),
          child: Text(L.t(lang, 'navHome')),
        ),
        const SizedBox(height: 10),
        OutlinedButton(
          onPressed: () => context.pushReplacement('/camera'),
          child: Text(L.t(lang, 'newCheck')),
        ),
      ],
    );
  }
}
