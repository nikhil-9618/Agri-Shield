import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/models.dart';

/// Everything that must survive app restarts lives here: language + account,
/// saved diagnoses (viewable offline), the pending upload queue, a weather
/// snapshot, and the generated account credentials used for silent sign-in.
class LocalStore {
  LocalStore(this._prefs);

  final SharedPreferences _prefs;

  static const _kSettings = 'settings_v1';
  static const _kSaved = 'saved_diagnoses_v1';
  static const _kQueue = 'upload_queue_v1';
  static const _kWeather = 'weather_cache_v1';
  static const _kPhone = 'account_phone';
  static const _kPassword = 'account_password';

  // ------------------------------------------------------------------ settings
  AppSettings loadSettings() {
    final raw = _prefs.getString(_kSettings);
    if (raw == null || raw.isEmpty) return const AppSettings();
    try {
      return AppSettings.fromJson(Map<String, dynamic>.from(jsonDecode(raw) as Map));
    } catch (_) {
      return const AppSettings();
    }
  }

  Future<void> saveSettings(AppSettings settings) =>
      _prefs.setString(_kSettings, jsonEncode(settings.toJson()));

  Future<void> clearSettings() => _prefs.remove(_kSettings);

  String? get accountPhone => _prefs.getString(_kPhone);
  String? get accountPassword => _prefs.getString(_kPassword);

  Future<void> saveAccountCredentials(String phone, String password) async {
    await _prefs.setString(_kPhone, phone);
    await _prefs.setString(_kPassword, password);
  }

  Future<void> clearAccount() async {
    await _prefs.remove(_kPhone);
    await _prefs.remove(_kPassword);
    await _prefs.remove(_kSettings);
  }

  // ------------------------------------------------------------------- history
  List<Diagnosis> loadSaved() {
    final raw = _prefs.getString(_kSaved);
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = jsonDecode(raw) as List;
      return list
          .map((e) => Diagnosis.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> saveSaved(List<Diagnosis> items) => _prefs.setString(
        _kSaved,
        jsonEncode(items.take(200).map((e) => e.toJson()).toList()),
      );

  // --------------------------------------------------------------------- queue
  List<QueuedUpload> loadQueue() {
    final raw = _prefs.getString(_kQueue);
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = jsonDecode(raw) as List;
      return list
          .map((e) => QueuedUpload.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> saveQueue(List<QueuedUpload> items) => _prefs.setString(
        _kQueue,
        jsonEncode(items.map((e) => e.toJson()).toList()),
      );

  /// Copies a captured image into app storage so it survives cache cleanup.
  Future<String> persistImage(File source) async {
    final dir = await getApplicationDocumentsDirectory();
    final images = Directory('${dir.path}/leaf_images');
    if (!images.existsSync()) images.createSync(recursive: true);
    final name = 'leaf_${DateTime.now().microsecondsSinceEpoch}.jpg';
    final target = File('${images.path}/$name');
    await source.copy(target.path);
    return target.path;
  }

  // ------------------------------------------------------------------- weather
  Map<String, dynamic>? loadWeather() {
    final raw = _prefs.getString(_kWeather);
    if (raw == null || raw.isEmpty) return null;
    try {
      return Map<String, dynamic>.from(jsonDecode(raw) as Map);
    } catch (_) {
      return null;
    }
  }

  Future<void> saveWeather(Map<String, dynamic> json) =>
      _prefs.setString(_kWeather, jsonEncode(json));
}
