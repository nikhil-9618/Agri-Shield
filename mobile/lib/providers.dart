import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'core/api_client.dart';
import 'core/local_store.dart';
import 'core/on_device_classifier.dart';
import 'core/speech.dart';
import 'models/models.dart';

/// Overridden in main() with the real instance so settings load synchronously.
final prefsProvider = Provider<SharedPreferences>(
  (ref) => throw UnimplementedError('prefsProvider must be overridden'),
);

final storeProvider = Provider<LocalStore>((ref) => LocalStore(ref.watch(prefsProvider)));

final speechProvider = Provider<SpeechService>((ref) {
  final service = SpeechService();
  ref.onDispose(service.stop);
  return service;
});

class AppState {
  final AppSettings settings;
  final List<Diagnosis> saved;
  final List<QueuedUpload> queue;
  final bool busy;
  final String? notice;

  const AppState({
    required this.settings,
    required this.saved,
    required this.queue,
    this.busy = false,
    this.notice,
  });

  String get language => settings.language;
  bool get onboarded => settings.onboarded;
  String get farmerName =>
      (settings.user?.name ?? '').trim() == 'Farmer' ? '' : (settings.user?.name ?? '');

  AppState copyWith({
    AppSettings? settings,
    List<Diagnosis>? saved,
    List<QueuedUpload>? queue,
    bool? busy,
    String? notice,
    bool clearNotice = false,
  }) =>
      AppState(
        settings: settings ?? this.settings,
        saved: saved ?? this.saved,
        queue: queue ?? this.queue,
        busy: busy ?? this.busy,
        notice: clearNotice ? null : (notice ?? this.notice),
      );
}

class AppController extends Notifier<AppState> {
  @override
  AppState build() {
    final store = ref.watch(storeProvider);
    return AppState(
      settings: store.loadSettings(),
      saved: store.loadSaved(),
      queue: store.loadQueue(),
    );
  }

  LocalStore get _store => ref.read(storeProvider);
  ApiClient get _api => ref.read(apiProvider);
  OnDeviceClassifier get _onDevice => ref.read(onDeviceClassifierProvider);

  int _newQueueId() => DateTime.now().microsecondsSinceEpoch;

  Future<void> setLanguage(String language) async {
    final settings = state.settings.copyWith(language: normalizeLang(language));
    state = state.copyWith(settings: settings);
    await _store.saveSettings(settings);
  }

  Future<void> markOnboarded() async {
    final settings = state.settings.copyWith(onboarded: true);
    state = state.copyWith(settings: settings);
    await _store.saveSettings(settings);
  }

  Future<void> setServerUrl(String url) async {
    var clean = url.trim();
    if (clean.endsWith('/')) clean = clean.substring(0, clean.length - 1);
    if (clean.isEmpty) return;
    final settings = state.settings.copyWith(serverUrl: clean);
    state = state.copyWith(settings: settings);
    await _store.saveSettings(settings);
  }

  void showNotice(String? text) {
    state = text == null
        ? state.copyWith(clearNotice: true)
        : state.copyWith(notice: text);
  }

  // ------------------------------------------------------------------ account
  /// Silent account provisioning: no phone number, no password to remember.
  /// Returns true when the phone is signed in and reachable.
  Future<bool> ensureAccount() async {
    if (state.busy) return state.settings.signedIn;
    state = state.copyWith(busy: true, clearNotice: true);
    try {
      if (state.settings.signedIn) {
        try {
          final user = await _api.me();
          await _persistUser(user);
          return true;
        } on ApiException catch (e) {
          if (!e.isAuthError) return false;
          final settings = state.settings.copyWith(token: '');
          state = state.copyWith(settings: settings);
          await _store.saveSettings(settings);
        }
      }

      final phone = _store.accountPhone;
      final password = _store.accountPassword;
      AuthResult result;
      if (phone != null && password != null) {
        try {
          result = await _api.login(phone: phone, password: password);
        } on ApiException catch (e) {
          if (e.status == 0) return false;
          final fresh = _randomPassword();
          result = await _api.registerAccount(
            language: state.settings.language,
            password: fresh,
          );
        }
      } else {
        result = await _api.registerAccount(
          language: state.settings.language,
          password: _randomPassword(),
        );
      }
      if (result.phone != null && result.password != null) {
        await _store.saveAccountCredentials(result.phone!, result.password!);
      }
      final settings = state.settings.copyWith(token: result.token, user: result.user);
      state = state.copyWith(settings: settings);
      await _store.saveSettings(settings);
      return true;
    } on ApiException {
      return false;
    } finally {
      state = state.copyWith(busy: false);
    }
  }

  String _randomPassword() {
    const chars = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    final rnd = Random.secure();
    return List.generate(20, (_) => chars[rnd.nextInt(chars.length)]).join();
  }

  Future<void> _persistUser(UserProfile user) async {
    final settings = state.settings.copyWith(user: user, language: user.language);
    state = state.copyWith(settings: settings);
    await _store.saveSettings(settings);
  }

  Future<bool> saveProfile({
    String? name,
    String? village,
    String? language,
  }) async {
    final changes = <String, dynamic>{
      if (name != null && name.trim().isNotEmpty) 'name': name.trim(),
      'village': ?village?.trim(),
      'language': ?language,
    };
    if (changes.isEmpty) return true;

    final local = state.settings.copyWith(
      language: language != null ? normalizeLang(language) : null,
      user: state.settings.user == null
          ? null
          : UserProfile(
              id: state.settings.user!.id,
              phone: state.settings.user!.phone,
              name: (changes['name'] as String?) ?? state.settings.user!.name,
              language: language != null
                  ? normalizeLang(language)
                  : state.settings.user!.language,
              village: (changes['village'] as String?) ?? state.settings.user!.village,
              state: state.settings.user!.state,
            ),
    );
    state = state.copyWith(settings: local);
    await _store.saveSettings(local);

    if (!state.settings.signedIn) {
      await ensureAccount();
    }
    if (!state.settings.signedIn) return false;
    try {
      final user = await _api.updateProfile(changes);
      await _persistUser(user);
      return true;
    } on ApiException {
      return false;
    }
  }

  // ---------------------------------------------------------------- diagnosis
  void _addSaved(Diagnosis diagnosis) {
    final items = [diagnosis, ...state.saved];
    state = state.copyWith(saved: items);
    _store.saveSaved(items);
  }

  Future<void> _enqueue(String imagePath, String language) async {
    final item = QueuedUpload(
      id: '${_newQueueId()}',
      imagePath: imagePath,
      language: language,
      createdAt: DateTime.now(),
    );
    final queue = [...state.queue, item];
    state = state.copyWith(queue: queue);
    await _store.saveQueue(queue);
  }

  /// Diagnoses a leaf photo. The trained model is bundled with the app, so the
  /// phone answers immediately with no network. The API is the fallback on old
  /// devices, and the queue is the last resort; the app never fakes a result.
  Future<Diagnosis?> diagnose({required File image, String? language}) async {
    final lang = normalizeLang(language ?? state.language);
    final localPath = await _store.persistImage(image);

    try {
      final diagnosis = await _onDevice.classify(
        await image.readAsBytes(),
        lang,
        localImagePath: localPath,
      );
      _addSaved(diagnosis);
      return diagnosis;
    } on OnDeviceException catch (e) {
      if (e.code == 'invalid_image') {
        throw ApiException('invalid_image', e.message, 422);
      }
      // Model unavailable on this device: try the API below.
    } catch (_) {
      // Unexpected on-device failure: try the API below rather than guessing.
    }

    final online = await ensureAccount();
    if (!online) {
      await _enqueue(localPath, lang);
      return null;
    }
    try {
      final diagnosis = await _api.predict(await image.readAsBytes(), image.path.split('/').last, lang);
      final withImage = diagnosis.copyWith(localImagePath: localPath);
      _addSaved(withImage);
      return withImage;
    } on ApiException catch (e) {
      if (e.status == 0) {
        await _enqueue(localPath, lang);
        return null;
      }
      rethrow;
    }
  }

  /// Processes photos left over from older builds when the app opens. With the
  /// bundled model these are diagnosed locally; the API is only a fallback.
  Future<int> syncQueue() async {
    if (state.queue.isEmpty) return 0;

    var done = 0;
    var onlineChecked = false;
    var online = false;
    final remaining = [...state.queue];
    for (final item in [...remaining]) {
      final file = File(item.imagePath);
      if (!file.existsSync()) {
        remaining.removeWhere((e) => e.id == item.id);
        continue;
      }
      try {
        final local = await _onDevice.classify(
          await file.readAsBytes(),
          item.language,
          localImagePath: item.imagePath,
        );
        _addSaved(local);
        remaining.removeWhere((e) => e.id == item.id);
        done++;
        continue;
      } on OnDeviceException catch (e) {
        if (e.code == 'invalid_image') {
          remaining.removeWhere((e) => e.id == item.id);
          continue;
        }
      } catch (_) {
        // Fall through to the API.
      }

      if (!onlineChecked) {
        onlineChecked = true;
        online = await ensureAccount();
      }
      if (!online) break;
      try {
        final diagnosis =
            await _api.predict(await file.readAsBytes(), file.path.split('/').last, item.language);
        _addSaved(diagnosis.copyWith(localImagePath: item.imagePath));
        remaining.removeWhere((e) => e.id == item.id);
        done++;
      } on ApiException catch (e) {
        if (e.status == 0) break; // still offline, stop and keep the queue
        if (e.status == 422) {
          remaining.removeWhere((x) => x.id == item.id); // unreadable forever
          continue;
        }
        break;
      }
    }
    state = state.copyWith(queue: remaining);
    await _store.saveQueue(remaining);
    return done;
  }

  // ------------------------------------------------------------------ weather
  Future<void> cacheWeather(WeatherSnapshot snapshot) =>
      _store.saveWeather(jsonDecode(jsonEncode(snapshot.toJson())) as Map<String, dynamic>);

  WeatherSnapshot? cachedWeather() {
    final json = _store.loadWeather();
    if (json == null) return null;
    try {
      return WeatherSnapshot.fromJson(json);
    } catch (_) {
      return null;
    }
  }

  /// Loads a saved advisory from bundled assets so offline history stays readable.
  Future<Map<String, dynamic>?> localAdvisory(String diseaseKey, String lang) async {
    try {
      final raw = await rootBundleLoadString('assets/advisory/diseases/$diseaseKey.json');
      if (raw == null) return null;
      final data = jsonDecode(raw) as Map<String, dynamic>;
      final blocks = (data['l'] as Map?) ?? {};
      final block = (blocks[lang] ?? blocks['en'] ?? {}) as Map;
      return Map<String, dynamic>.from(block);
    } catch (_) {
      return null;
    }
  }
}

/// Small indirection so tests/UI can stay free of asset import noise.
Future<String?> rootBundleLoadString(String path) async {
  try {
    // ignore: avoid_dynamic_calls
    return await _assetLoader(path);
  } catch (_) {
    return null;
  }
}

Future<String?> Function(String) _assetLoader = (path) async => null;

void registerAssetLoader(Future<String?> Function(String) loader) {
  _assetLoader = loader;
}

final appProvider = NotifierProvider<AppController, AppState>(AppController.new);

final onDeviceClassifierProvider =
    Provider<OnDeviceClassifier>((ref) => OnDeviceClassifier());

final apiProvider = Provider<ApiClient>((ref) {
  final settings = ref.watch(appProvider.select((s) => s.settings));
  return ApiClient(
    baseUrl: settings.serverUrl,
    tokenProvider: () => ref.read(appProvider).settings.token,
  );
});

final connectionProvider = FutureProvider<bool>((ref) async {
  final api = ref.watch(apiProvider);
  return api.health();
});
