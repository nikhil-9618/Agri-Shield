import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/theme.dart';
import '../providers.dart';
import '../widgets/agrishield_logo.dart';

/// Branded first frame while the app restores the farmer's language and history.
class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _fade;
  late final Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    );
    _fade = Tween<double>(begin: 0.65, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeOut),
    );
    _scale = Tween<double>(begin: 0.92, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic),
    );
    _controller.forward();
    // Start the hold after the first frame so slow devices still see the brand
    // while the SVG asset is decoded.
    WidgetsBinding.instance.addPostFrameCallback((_) => _continue());
  }

  Future<void> _continue() async {
    await Future<void>.delayed(const Duration(milliseconds: 2200));
    if (!mounted) return;
    context.go(ref.read(appProvider).onboarded ? '/home' : '/language');
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AgriColors.background,
      body: SafeArea(
        child: Center(
          child: FadeTransition(
            opacity: _fade,
            child: ScaleTransition(
              scale: _scale,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const AgriShieldLogo(width: 152, height: 152),
                  const SizedBox(height: 18),
                  const Text(
                    'AgriShield',
                    style: TextStyle(
                      fontSize: 38,
                      fontWeight: FontWeight.w900,
                      letterSpacing: -1.0,
                      color: AgriBrand.navy,
                    ),
                  ),
                  const SizedBox(height: 10),
                  const Text(
                    'Smart Farming. Healthy Crops.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      color: AgriBrand.green,
                    ),
                  ),
                  const SizedBox(height: 26),
                  AnimatedBuilder(
                    animation: _controller,
                    builder: (_, _) => Container(
                      height: 4,
                      width: 96 * _controller.value,
                      decoration: BoxDecoration(
                        color: AgriBrand.fresh,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
