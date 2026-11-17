import 'package:material_ui/material_ui.dart';

/// AgriShield design tokens — deep agricultural green, warm white, high contrast.
/// Everything is sized for outdoor use on cheap phones: large text, large touch
/// targets (>= 64dp for primary actions), minimal animation.
/// Brand palette for the AgriShield mark and interface accents.
class AgriBrand {
  static const navy = Color(0xFF0B2635);
  static const green = Color(0xFF087A55);
  static const fresh = Color(0xFFC8FF72);
  static const mint = Color(0xFF5CE6B0);
  static const gold = Color(0xFFF5A623);
}

class AgriColors {
  static const primary = AgriBrand.green;
  static const primaryDark = AgriBrand.navy;
  static const secondary = AgriBrand.mint;
  static const secondarySoft = Color(0xFFDDF3E7);
  static const background = Color(0xFFFFFDF6); // warm white
  static const surface = Colors.white;
  static const ink = Color(0xFF1B1B1B);
  static const inkSoft = Color(0xFF4A4A4A);

  static const healthy = Color(0xFF2E7D32);
  static const healthySoft = Color(0xFFE3F2E1);
  static const warning = Color(0xFFF9A825);
  static const warningSoft = Color(0xFFFFF3D6);
  static const urgent = Color(0xFFC62828);
  static const urgentSoft = Color(0xFFFFE3E1);

  static Color level(String value) => switch (value) {
        'green' => healthy,
        'red' => urgent,
        _ => warning,
      };

  static Color levelSoft(String value) => switch (value) {
        'green' => healthySoft,
        'red' => urgentSoft,
        _ => warningSoft,
      };
}

class AgriTheme {
  static const double touch = 68; // primary button height
  static const double gap = 16;

  static ThemeData build() {
    final base = ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: AgriColors.primary,
        primary: AgriColors.primary,
        secondary: AgriColors.secondary,
        surface: AgriColors.surface,
        brightness: Brightness.light,
      ),
      scaffoldBackgroundColor: AgriColors.background,
      visualDensity: VisualDensity.standard,
    );

    return base.copyWith(
      textTheme: base.textTheme.copyWith(
        displaySmall: const TextStyle(
            fontSize: 34, fontWeight: FontWeight.w800, color: AgriColors.ink, height: 1.15),
        headlineMedium: const TextStyle(
            fontSize: 27, fontWeight: FontWeight.w800, color: AgriColors.ink, height: 1.2),
        titleLarge: const TextStyle(
            fontSize: 22, fontWeight: FontWeight.w700, color: AgriColors.ink, height: 1.25),
        bodyLarge: const TextStyle(
            fontSize: 20, fontWeight: FontWeight.w600, color: AgriColors.ink, height: 1.35),
        bodyMedium: const TextStyle(
            fontSize: 18, fontWeight: FontWeight.w500, color: AgriColors.inkSoft, height: 1.35),
        labelLarge: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AgriColors.primary,
        foregroundColor: Colors.white,
        centerTitle: false,
        elevation: 0,
        toolbarHeight: 68,
        titleTextStyle: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: Colors.white),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(touch),
          textStyle: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
          backgroundColor: AgriColors.primary,
          foregroundColor: Colors.white,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size.fromHeight(60),
          textStyle: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
          side: const BorderSide(color: AgriColors.primary, width: 2),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        ),
      ),
      cardTheme: CardThemeData(
        color: AgriColors.surface,
        elevation: 1.5,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(22),
          side: const BorderSide(color: Color(0xFFE7E3D5)),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        height: 76,
        backgroundColor: Colors.white,
        indicatorColor: AgriColors.secondarySoft,
        labelTextStyle: WidgetStateProperty.all(
          const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AgriColors.ink),
        ),
      ),
      snackBarTheme: const SnackBarThemeData(
        backgroundColor: AgriColors.primaryDark,
        contentTextStyle: TextStyle(fontSize: 19, color: Colors.white),
        behavior: SnackBarBehavior.floating,
      ),
      dividerTheme: const DividerThemeData(color: Color(0xFFE7E3D5)),
      chipTheme: base.chipTheme.copyWith(
        labelStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      ),
    );
  }
}
