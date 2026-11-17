import 'package:material_ui/material_ui.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../core/theme.dart';

/// The single, reusable AgriShield mark.
///
/// The SVG is drawn as supplied: no tint, crop or stretch. [width] and
/// [height] control the icon box; [showWordmark] adds the brand name beside it.
class AgriShieldLogo extends StatelessWidget {
  static const String asset = 'assets/images/agrishield_logo.svg';

  final double width;
  final double height;
  final bool showWordmark;
  final Color? wordmarkColor;

  const AgriShieldLogo({
    super.key,
    this.width = 56,
    this.height = 56,
    this.showWordmark = false,
    this.wordmarkColor,
  });

  @override
  Widget build(BuildContext context) {
    final mark = SvgPicture.asset(
      asset,
      width: width,
      height: height,
      fit: BoxFit.contain,
      semanticsLabel: 'AgriShield',
    );

    if (!showWordmark) return mark;

    final isDark = Theme.of(context).brightness == Brightness.dark;
    final color = wordmarkColor ?? (isDark ? Colors.white : AgriBrand.navy);
    final fontSize = (height * 0.58).clamp(20.0, 34.0);

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        mark,
        SizedBox(width: width * 0.22),
        Text(
          'AgriShield',
          maxLines: 1,
          style: TextStyle(
            color: color,
            fontSize: fontSize,
            height: 1.0,
            fontWeight: FontWeight.w800,
            letterSpacing: -0.6,
          ),
        ),
      ],
    );
  }
}
