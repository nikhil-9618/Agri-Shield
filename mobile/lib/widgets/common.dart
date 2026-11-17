import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/strings.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../providers.dart';

const EdgeInsets kPad = EdgeInsets.symmetric(horizontal: 18, vertical: 14);

/// Big, high-contrast primary action used on the home screen.
class ActionTile extends ConsumerWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;
  final VoidCallback onTap;
  final String speakText;

  const ActionTile({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.color,
    required this.onTap,
    required this.speakText,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lang = ref.watch(appProvider.select((s) => s.language));
    return Semantics(
      button: true,
      label: '$title. $subtitle',
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              children: [
                Container(
                  width: 82,
                  height: 82,
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.14),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Icon(icon, size: 50, color: color),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title,
                          style: const TextStyle(
                              fontSize: 23,
                              fontWeight: FontWeight.w800,
                              height: 1.15)),
                      const SizedBox(height: 4),
                      Text(subtitle,
                          style: TextStyle(
                              fontSize: 17, color: AgriColors.inkSoft, height: 1.2)),
                    ],
                  ),
                ),
                SpeakerButton(text: speakText, language: lang, compact: true),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Speaker button that reads any text aloud in the selected language.
class SpeakerButton extends ConsumerStatefulWidget {
  final String text;
  final String language;
  final bool compact;
  final Color? color;

  const SpeakerButton({
    super.key,
    required this.text,
    required this.language,
    this.compact = false,
    this.color,
  });

  @override
  ConsumerState<SpeakerButton> createState() => _SpeakerButtonState();
}

class _SpeakerButtonState extends ConsumerState<SpeakerButton> {
  bool _speaking = false;

  Future<void> _toggle() async {
    final speech = ref.read(speechProvider);
    if (_speaking) {
      await speech.stop();
      if (mounted) setState(() => _speaking = false);
      return;
    }
    setState(() => _speaking = true);
    final ok = await speech.speak(widget.text, widget.language);
    if (mounted) {
      setState(() => _speaking = false);
      if (!ok) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(L.t(widget.language, 'voiceNotAvailable'))),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = widget.color ?? AgriColors.primary;
    return Semantics(
      button: true,
      label: L.t(widget.language, 'speakAloud'),
      child: IconButton(
        onPressed: _toggle,
        iconSize: widget.compact ? 30 : 34,
        tooltip: L.t(widget.language, 'speakAloud'),
        style: IconButton.styleFrom(
          backgroundColor: color.withValues(alpha: 0.12),
          minimumSize: Size(widget.compact ? 54 : 60, widget.compact ? 54 : 60),
        ),
        icon: Icon(_speaking ? Icons.stop_circle : Icons.volume_up_rounded, color: color),
      ),
    );
  }
}

/// Traffic-light result banner: green / yellow / red with a large symbol.
class LevelBanner extends StatelessWidget {
  final String level;
  final String title;
  final String language;

  const LevelBanner({
    super.key,
    required this.level,
    required this.title,
    required this.language,
  });

  @override
  Widget build(BuildContext context) {
    final color = AgriColors.level(level);
    final soft = AgriColors.levelSoft(level);
    final icon = switch (level) {
      'green' => Icons.verified_rounded,
      'red' => Icons.warning_rounded,
      _ => Icons.help_rounded,
    };
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 20),
      decoration: BoxDecoration(
        color: soft,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: color, width: 3),
      ),
      child: Row(
        children: [
          Icon(icon, size: 64, color: color),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: TextStyle(
                        fontSize: 26, fontWeight: FontWeight.w900, color: color)),
                const SizedBox(height: 4),
                Text(
                  level == 'green'
                      ? L.t(language, 'levelHealthy')
                      : level == 'red'
                          ? L.t(language, 'levelUrgent')
                          : L.t(language, 'levelWarning'),
                  style: TextStyle(
                      fontSize: 18, fontWeight: FontWeight.w700, color: color),
                ),
              ],
            ),
          ),
          SpeakerButton(text: title, language: language, color: color),
        ],
      ),
    );
  }
}

/// Advisory section with a picture-like icon and a large readable sentence.
class SectionCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String body;
  final Color color;
  final String language;

  const SectionCard({
    super.key,
    required this.icon,
    required this.title,
    required this.body,
    required this.color,
    required this.language,
  });

  @override
  Widget build(BuildContext context) {
    if (body.trim().isEmpty) return const SizedBox.shrink();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Icon(icon, size: 32, color: color),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(title,
                            style: const TextStyle(
                                fontSize: 20, fontWeight: FontWeight.w800)),
                      ),
                      SpeakerButton(
                        text: '$title. $body',
                        language: language,
                        compact: true,
                        color: color,
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(body, style: const TextStyle(fontSize: 19, height: 1.35)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class AdvisorySections extends StatelessWidget {
  final AdvisoryBlock block;
  final String language;

  const AdvisorySections({super.key, required this.block, required this.language});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        SectionCard(
          icon: Icons.visibility_rounded,
          title: L.t(language, 'sectionSigns'),
          body: block.signs,
          color: AgriColors.warning,
          language: language,
        ),
        const SizedBox(height: 12),
        SectionCard(
          icon: Icons.pan_tool_alt_rounded,
          title: L.t(language, 'sectionDoNow'),
          body: block.doNow,
          color: AgriColors.primary,
          language: language,
        ),
        const SizedBox(height: 12),
        SectionCard(
          icon: Icons.block_rounded,
          title: L.t(language, 'sectionAvoid'),
          body: block.avoid,
          color: AgriColors.urgent,
          language: language,
        ),
        const SizedBox(height: 12),
        SectionCard(
          icon: Icons.shield_rounded,
          title: L.t(language, 'sectionPrevent'),
          body: block.prevention,
          color: AgriColors.healthy,
          language: language,
        ),
        const SizedBox(height: 12),
        SectionCard(
          icon: Icons.support_agent_rounded,
          title: L.t(language, 'sectionExpert'),
          body: block.expert,
          color: AgriColors.primaryDark,
          language: language,
        ),
      ],
    );
  }
}

class ErrorView extends StatelessWidget {
  final String message;
  final String language;
  final VoidCallback? onRetry;

  const ErrorView({
    super.key,
    required this.message,
    required this.language,
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.cloud_off_rounded, size: 84, color: AgriColors.warning),
          const SizedBox(height: 16),
          Text(message,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w600)),
          if (onRetry != null) ...[
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh_rounded, size: 28),
              label: Text(L.t(language, 'commonRetry')),
            ),
          ],
        ],
      ),
    );
  }
}

class InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;

  const InfoChip({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
    this.color = AgriColors.primary,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 28, color: color),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label,
                  style: TextStyle(fontSize: 14, color: color, fontWeight: FontWeight.w700)),
              Text(value,
                  style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w800)),
            ],
          ),
        ],
      ),
    );
  }
}

class OfflineBanner extends StatelessWidget {
  final int pending;
  final String language;
  final VoidCallback? onSync;
  final bool syncing;

  const OfflineBanner({
    super.key,
    required this.pending,
    required this.language,
    this.onSync,
    this.syncing = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: kPad,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AgriColors.warningSoft,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AgriColors.warning),
      ),
      child: Row(
        children: [
          const Icon(Icons.cloud_off_rounded, color: AgriColors.warning, size: 34),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              L.t(language, 'pendingBadge', vars: {'count': '$pending'}),
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
            ),
          ),
          if (onSync != null)
            TextButton(
              onPressed: syncing ? null : onSync,
              child: Text(syncing ? L.t(language, 'syncing') : L.t(language, 'syncNow')),
            ),
        ],
      ),
    );
  }
}

void showBigSnack(BuildContext context, String message) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(message, style: const TextStyle(fontSize: 19))));
}
