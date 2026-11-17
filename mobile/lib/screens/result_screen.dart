import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/strings.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../providers.dart';
import '../widgets/common.dart';

class ResultScreen extends ConsumerStatefulWidget {
  final Diagnosis? diagnosis;
  const ResultScreen({super.key, this.diagnosis});

  @override
  ConsumerState<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends ConsumerState<ResultScreen> {
  bool _showHeatmap = false;

  Diagnosis? get _d => widget.diagnosis;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _speakResult());
  }

  Future<void> _speakResult() async {
    final d = _d;
    if (d == null) return;
    final lang = ref.read(appProvider).language;
    final advisory = d.advisory;
    final title = advisory.name.isNotEmpty ? advisory.name : d.diseaseName;
    final text = d.status == 'unclear'
        ? '${d.message}. ${L.t(lang, 'newCheck')}.'
        : '$title. ${d.message}. ${advisory.signs}. ${advisory.doNow}. ${advisory.expert}.';
    await ref.read(speechProvider).speak(text, lang);
  }

  Uint8List? _heatmapBytes() {
    final raw = _d?.gradcamBase64;
    if (raw == null || raw.isEmpty) return null;
    final cleaned = raw.contains(',') ? raw.split(',').last : raw;
    try {
      return base64Decode(cleaned);
    } catch (_) {
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _d;
    final lang = ref.watch(appProvider.select((s) => s.language));
    if (d == null) {
      return Scaffold(
        appBar: AppBar(title: Text(L.t(lang, 'resultTitle'))),
        body: ErrorView(
          message: L.t(lang, 'commonError'),
          language: lang,
          onRetry: () => context.go('/home'),
        ),
      );
    }

    final title = d.advisory.name.isNotEmpty ? d.advisory.name : d.diseaseName;
    final soft = AgriColors.levelSoft(d.level);
    final color = AgriColors.level(d.level);
    final heatmap = _heatmapBytes();
    final imageFile = d.localImagePath != null ? File(d.localImagePath!) : null;

    return Scaffold(
      appBar: AppBar(
        title: Text(L.t(lang, 'resultTitle')),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, size: 30),
          onPressed: () => context.go('/home'),
        ),
        actions: [
          SpeakerButton(
            text: '$title. ${d.message}',
            language: lang,
            color: Colors.white,
          ),
          const SizedBox(width: 6),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
        children: [
          LevelBanner(level: d.level, title: title, language: lang),
          const SizedBox(height: 8),
          if (d.message.isNotEmpty)
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: color.withValues(alpha: 0.4)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.info_rounded, color: color, size: 30),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      d.message,
                      style: const TextStyle(fontSize: 20, height: 1.3),
                    ),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 14),
          if (imageFile != null && imageFile.existsSync())
            Stack(
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(22),
                  child: _showHeatmap && heatmap != null
                      ? Image.memory(
                          heatmap,
                          height: 260,
                          width: double.infinity,
                          fit: BoxFit.cover,
                        )
                      : Image.file(
                          imageFile,
                          height: 260,
                          width: double.infinity,
                          fit: BoxFit.cover,
                        ),
                ),
                if (heatmap != null)
                  Positioned(
                    right: 10,
                    bottom: 10,
                    child: FilledButton.tonalIcon(
                      onPressed: () => setState(() => _showHeatmap = !_showHeatmap),
                      icon: Icon(
                        _showHeatmap ? Icons.image_rounded : Icons.local_fire_department_rounded,
                        size: 26,
                      ),
                      label: Text(
                        L.t(lang, _showHeatmap ? 'heatmapHide' : 'heatmapShow'),
                        style: const TextStyle(fontSize: 17),
                      ),
                    ),
                  ),
              ],
            ),
          if (heatmap != null) ...[
            const SizedBox(height: 6),
            Text(
              L.t(lang, 'heatmapExplain'),
              style: const TextStyle(fontSize: 16, color: AgriColors.inkSoft),
            ),
          ],
          const SizedBox(height: 16),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              InfoChip(
                icon: Icons.eco_rounded,
                label: d.cropName.isEmpty ? d.cropKey : d.cropName,
                value: d.diseaseName,
                color: color,
              ),
              InfoChip(
                icon: Icons.verified_rounded,
                label: L.t(lang, 'confidenceLabel'),
                value: '${(d.confidence * 100).round()}%',
                color: d.level == 'green' ? AgriColors.primary : AgriColors.warning,
              ),
            ],
          ),
          const SizedBox(height: 18),
          if (d.top3.isNotEmpty) _TopThree(diagnosis: d, language: lang),
          const SizedBox(height: 18),
          if (d.status != 'unclear' && d.advisory.name.isNotEmpty) ...[
            AdvisorySections(block: d.advisory, language: lang),
            const SizedBox(height: 16),
          ],
          if (d.status == 'unclear') ...[
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: soft,
                borderRadius: BorderRadius.circular(18),
              ),
              child: Row(
                children: [
                  Icon(Icons.photo_camera_rounded, color: color, size: 34),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      L.t(lang, 'newCheck'),
                      style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
          ],
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFFFFF8E1),
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: AgriColors.warning),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.warning_amber_rounded, color: AgriColors.warning, size: 32),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    d.disclaimer.isNotEmpty ? d.disclaimer : L.t(lang, 'localDisclaimer'),
                    style: const TextStyle(fontSize: 17, height: 1.35),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: () => context.pushReplacement('/camera'),
            icon: const Icon(Icons.photo_camera_rounded, size: 28),
            label: Text(L.t(lang, 'newCheck')),
          ),
          const SizedBox(height: 10),
          OutlinedButton.icon(
            onPressed: () => context.go('/help'),
            icon: const Icon(Icons.support_agent_rounded, size: 28),
            label: Text(L.t(lang, 'expertButton')),
          ),
          const SizedBox(height: 10),
          TextButton.icon(
            onPressed: _speakResult,
            icon: const Icon(Icons.replay_rounded, size: 24),
            label: Text(L.t(lang, 'repeatAudio'), style: const TextStyle(fontSize: 18)),
          ),
        ],
      ),
    );
  }
}

class _TopThree extends StatelessWidget {
  final Diagnosis diagnosis;
  final String language;
  const _TopThree({required this.diagnosis, required this.language});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              L.t(language, 'topThree'),
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 12),
            ...diagnosis.top3.map((p) {
              final fraction = p.confidence.clamp(0.0, 1.0);
              final isTop = p.key == diagnosis.diseaseKey;
              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            p.diseaseName.isEmpty ? p.key : p.diseaseName,
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: isTop ? FontWeight.w800 : FontWeight.w500,
                            ),
                          ),
                        ),
                        Text(
                          '${(p.confidence * 100).round()}%',
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: LinearProgressIndicator(
                        value: fraction,
                        minHeight: 12,
                        backgroundColor: const Color(0xFFEDEDED),
                        color: isTop ? AgriColors.primary : AgriColors.secondary,
                      ),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }
}
