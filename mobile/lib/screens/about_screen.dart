import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/strings.dart';
import '../core/theme.dart';
import '../providers.dart';
import '../widgets/agrishield_logo.dart';

class AboutScreen extends ConsumerWidget {
  const AboutScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lang = ref.watch(appProvider.select((s) => s.language));

    return Scaffold(
      appBar: AppBar(title: const Text('About AgriShield')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
        children: [
          const Center(
            child: AgriShieldLogo(width: 104, height: 104, showWordmark: true),
          ),
          const SizedBox(height: 18),
          const Text(
            'Smart Farming. Healthy Crops.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 21,
              fontWeight: FontWeight.w700,
              color: AgriBrand.green,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '${L.t(lang, 'helpVersion')} 1.2.0',
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 16, color: AgriColors.inkSoft),
          ),
          const SizedBox(height: 24),
          const Card(
            child: Padding(
              padding: EdgeInsets.all(18),
              child: Text(
                'AgriShield helps farmers check a crop leaf with a photo. '
                'The trained model runs on the phone, so the result is available '
                'even without internet. Advice is written in five languages and '
                'can be read aloud.',
                style: TextStyle(fontSize: 18, height: 1.4),
              ),
            ),
          ),
          const SizedBox(height: 18),
          const _Feature(
            icon: Icons.eco_rounded,
            color: AgriBrand.green,
            title: 'On-device crop check',
            body: '27 diseases across six crops, with a clear green, yellow or red result.',
          ),
          const SizedBox(height: 12),
          const _Feature(
            icon: Icons.record_voice_over_rounded,
            color: AgriBrand.mint,
            title: 'Five languages, spoken',
            body: 'Telugu, Hindi, English, Tamil and Kannada — no typing needed.',
          ),
          const SizedBox(height: 12),
          const _Feature(
            icon: Icons.wifi_off_rounded,
            color: AgriBrand.gold,
            title: 'Works in the field',
            body: 'Saved results, bundled advice and a local model keep the app useful offline.',
          ),
          const SizedBox(height: 24),
          const Text(
            'Brand palette',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 10),
          const Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              _Swatch('Deep Navy', AgriBrand.navy),
              _Swatch('Agri Green', AgriBrand.green),
              _Swatch('Fresh Growth', AgriBrand.fresh),
              _Swatch('AI Mint', AgriBrand.mint),
              _Swatch('Harvest Gold', AgriBrand.gold),
            ],
          ),
          const SizedBox(height: 24),
          Text(
            L.t(lang, 'localDisclaimer'),
            style: const TextStyle(fontSize: 15, color: AgriColors.inkSoft),
          ),
        ],
      ),
    );
  }
}

class _Feature extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String title;
  final String body;

  const _Feature({
    required this.icon,
    required this.color,
    required this.title,
    required this.body,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 36, color: color),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title,
                      style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w800)),
                  const SizedBox(height: 4),
                  Text(body,
                      style: const TextStyle(fontSize: 16, color: AgriColors.inkSoft)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Swatch extends StatelessWidget {
  final String label;
  final Color color;

  const _Swatch(this.label, this.color);

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 18,
          height: 18,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
            border: Border.all(color: const Color(0xFFE7E3D5)),
          ),
        ),
        const SizedBox(width: 6),
        Text(label, style: const TextStyle(fontSize: 14)),
      ],
    );
  }
}
