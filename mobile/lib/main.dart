import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';
import 'core/local_store.dart';
import 'providers.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);

  // Bundled advisory JSON is the offline knowledge base; the controller reads it
  // through this loader so widgets never depend on the asset bundle directly.
  registerAssetLoader((path) async {
    try {
      return await rootBundle.loadString(path);
    } catch (_) {
      return null;
    }
  });

  final prefs = await SharedPreferences.getInstance();
  final settings = LocalStore(prefs).loadSettings();

  runApp(
    ProviderScope(
      overrides: [prefsProvider.overrideWithValue(prefs)],
      child: AgriShieldApp(
        initialRoute: settings.onboarded ? '/home' : '/language',
      ),
    ),
  );
}
