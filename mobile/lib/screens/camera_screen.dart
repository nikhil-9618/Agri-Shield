import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../core/strings.dart';
import '../core/theme.dart';
import '../providers.dart';
import '../widgets/common.dart';

class CameraScreen extends ConsumerStatefulWidget {
  const CameraScreen({super.key});

  @override
  ConsumerState<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends ConsumerState<CameraScreen> {
  final ImagePicker _picker = ImagePicker();
  bool _busy = false;

  Future<void> _pick(ImageSource source) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final file = await _picker.pickImage(
        source: source,
        maxWidth: 1600,
        imageQuality: 88,
        preferredCameraDevice: CameraDevice.rear,
      );
      if (!mounted) return;
      if (file == null) return;
      context.push('/analysis', extra: file.path);
    } catch (e) {
      if (!mounted) return;
      showBigSnack(
        context,
        source == ImageSource.camera
            ? 'Camera not available on this phone. Use gallery.'
            : 'Could not open the gallery. Please try again.',
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final lang = ref.watch(appProvider.select((s) => s.language));
    final tips = [L.t(lang, 'cameraTip1'), L.t(lang, 'cameraTip2'), L.t(lang, 'cameraTip3')];

    return Scaffold(
      appBar: AppBar(
        title: Text(L.t(lang, 'cameraGuideTitle')),
        actions: [
          SpeakerButton(
            text: '${L.t(lang, 'cameraGuideTitle')}. ${tips.join('. ')}',
            language: lang,
            color: Colors.white,
          ),
          const SizedBox(width: 6),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(18),
                children: [
                  AspectRatio(
                    aspectRatio: 4 / 3,
                    child: Container(
                      decoration: BoxDecoration(
                        color: const Color(0xFF10240F),
                        borderRadius: BorderRadius.circular(26),
                        border: Border.all(color: AgriColors.secondary, width: 3),
                      ),
                      child: Stack(
                        children: [
                          Center(
                            child: Icon(
                              Icons.eco_rounded,
                              size: 170,
                              color: Colors.white.withValues(alpha: 0.18),
                            ),
                          ),
                          Positioned.fill(
                            child: Padding(
                              padding: const EdgeInsets.all(26),
                              child: Container(
                                decoration: BoxDecoration(
                                  border: Border.all(color: Colors.white70, width: 3),
                                  borderRadius: BorderRadius.circular(18),
                                ),
                              ),
                            ),
                          ),
                          Positioned(
                            left: 14,
                            bottom: 14,
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                              decoration: BoxDecoration(
                                color: Colors.black54,
                                borderRadius: BorderRadius.circular(14),
                              ),
                              child: Row(
                                children: [
                                  const Icon(Icons.workspace_premium_rounded,
                                      color: AgriColors.secondary, size: 26),
                                  const SizedBox(width: 6),
                                  Text(
                                    L.t(lang, 'cameraGuideTitle'),
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 16,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  ...tips.asMap().entries.map(
                        (entry) => Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Container(
                                width: 34,
                                height: 34,
                                alignment: Alignment.center,
                                decoration: const BoxDecoration(
                                  color: AgriColors.primary,
                                  shape: BoxShape.circle,
                                ),
                                child: Text(
                                  '${entry.key + 1}',
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 19,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Text(
                                  entry.value,
                                  style: const TextStyle(fontSize: 20, height: 1.3),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(18, 4, 18, 16),
              child: Column(
                children: [
                  Semantics(
                    button: true,
                    label: L.t(lang, 'takePhoto'),
                    child: InkWell(
                      onTap: _busy ? null : () => _pick(ImageSource.camera),
                      customBorder: const CircleBorder(),
                      child: Container(
                        width: 104,
                        height: 104,
                        decoration: BoxDecoration(
                          color: AgriColors.primary,
                          shape: BoxShape.circle,
                          border: Border.all(color: AgriColors.secondary, width: 6),
                        ),
                        child: _busy
                            ? const Padding(
                                padding: EdgeInsets.all(30),
                                child: CircularProgressIndicator(color: Colors.white),
                              )
                            : const Icon(Icons.photo_camera_rounded,
                                size: 52, color: Colors.white),
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    L.t(lang, 'takePhoto'),
                    style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
                    onPressed: _busy ? null : () => _pick(ImageSource.gallery),
                    icon: const Icon(Icons.photo_library_rounded, size: 28),
                    label: Text(L.t(lang, 'fromGallery')),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
