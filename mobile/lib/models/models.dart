import 'dart:convert';

const kLanguages = ['te', 'hi', 'en', 'ta', 'kn'];
const kDefaultLanguage = 'te';

String normalizeLang(String? lang) => kLanguages.contains(lang) ? lang! : kDefaultLanguage;

class UserProfile {
  final int id;
  final String phone;
  final String name;
  final String language;
  final String? village;
  final String? state;

  const UserProfile({
    required this.id,
    required this.phone,
    required this.name,
    required this.language,
    this.village,
    this.state,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) => UserProfile(
        id: json['id'] as int,
        phone: json['phone'] as String? ?? '',
        name: json['name'] as String? ?? '',
        language: normalizeLang(json['language'] as String?),
        village: json['village'] as String?,
        state: json['state'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'phone': phone,
        'name': name,
        'language': language,
        'village': village,
        'state': state,
      };
}

/// Cleans a server address typed by a helper: trims, adds `http://` when the
/// scheme is missing, drops trailing slashes. Returns null when the result is
/// not a usable http(s) URL with a host.
String? normalizeServerUrl(String input) {
  var clean = input.trim();
  if (clean.isEmpty) return null;
  if (!RegExp(r'^[a-zA-Z][a-zA-Z0-9+.-]*://').hasMatch(clean)) {
    clean = 'http://$clean';
  }
  final uri = Uri.tryParse(clean);
  if (uri == null ||
      (uri.scheme != 'http' && uri.scheme != 'https') ||
      uri.host.isEmpty ||
      uri.hasQuery ||
      uri.hasFragment) {
    return null;
  }
  while (clean.endsWith('/')) {
    clean = clean.substring(0, clean.length - 1);
  }
  return clean;
}

class AppSettings {
  final String language;
  final bool onboarded;
  final String? token;
  final UserProfile? user;
  final String serverUrl;

  const AppSettings({
    this.language = kDefaultLanguage,
    this.onboarded = false,
    this.token,
    this.user,
    this.serverUrl = const String.fromEnvironment(
      'AGRI_API_BASE_URL',
      defaultValue: '',
    ),
  });

  bool get signedIn => token != null && token!.isNotEmpty;

  AppSettings copyWith({
    String? language,
    bool? onboarded,
    String? token,
    UserProfile? user,
    String? serverUrl,
    bool clearUser = false,
  }) =>
      AppSettings(
        language: language ?? this.language,
        onboarded: onboarded ?? this.onboarded,
        token: token ?? this.token,
        user: clearUser ? null : (user ?? this.user),
        serverUrl: serverUrl ?? this.serverUrl,
      );

  Map<String, dynamic> toJson() => {
        'language': language,
        'onboarded': onboarded,
        'token': token,
        'user': user?.toJson(),
        'serverUrl': serverUrl,
      };

  factory AppSettings.fromJson(Map<String, dynamic> json) => AppSettings(
        language: normalizeLang(json['language'] as String?),
        onboarded: json['onboarded'] as bool? ?? false,
        token: json['token'] as String?,
        user: json['user'] == null
            ? null
            : UserProfile.fromJson(Map<String, dynamic>.from(json['user'] as Map)),
        serverUrl: json['serverUrl'] as String? ??
            const String.fromEnvironment('AGRI_API_BASE_URL', defaultValue: ''),
      );
}

class AdvisoryBlock {
  final String name;
  final String signs;
  final String doNow;
  final String avoid;
  final String prevention;
  final String expert;

  const AdvisoryBlock({
    required this.name,
    required this.signs,
    required this.doNow,
    required this.avoid,
    required this.prevention,
    required this.expert,
  });

  factory AdvisoryBlock.fromJson(Map<String, dynamic> j) => AdvisoryBlock(
        name: j['name'] as String? ?? '',
        signs: j['signs'] as String? ?? '',
        doNow: j['do_now'] as String? ?? '',
        avoid: j['avoid'] as String? ?? '',
        prevention: j['prevention'] as String? ?? '',
        expert: j['expert'] as String? ?? '',
      );

  Map<String, dynamic> toJson() => {
        'name': name,
        'signs': signs,
        'do_now': doNow,
        'avoid': avoid,
        'prevention': prevention,
        'expert': expert,
      };

  /// All sections spoken by the text-to-speech reader.
  String get spoken => '$name. $signs. $doNow. $prevention. $expert';
}

class Prediction {
  final String key;
  final String crop;
  final String disease;
  final double confidence;
  final String cropName;
  final String diseaseName;
  final bool isHealthy;

  const Prediction({
    required this.key,
    required this.crop,
    required this.disease,
    required this.confidence,
    required this.cropName,
    required this.diseaseName,
    required this.isHealthy,
  });

  factory Prediction.fromJson(Map<String, dynamic> j) => Prediction(
        key: j['key'] as String? ?? '',
        crop: j['crop'] as String? ?? '',
        disease: j['disease'] as String? ?? '',
        confidence: (j['confidence'] as num?)?.toDouble() ?? 0,
        cropName: j['crop_name'] as String? ?? '',
        diseaseName: j['disease_name'] as String? ?? '',
        isHealthy: j['is_healthy'] as bool? ?? false,
      );

  Map<String, dynamic> toJson() => {
        'key': key,
        'crop': crop,
        'disease': disease,
        'confidence': confidence,
        'crop_name': cropName,
        'disease_name': diseaseName,
        'is_healthy': isHealthy,
      };
}

class Diagnosis {
  final int? serverId;
  final DateTime createdAt;
  final String status; // diagnosed | unclear | queued
  final String level; // green | yellow | red
  final String language;
  final String cropKey;
  final String cropName;
  final String diseaseKey;
  final String diseaseName;
  final double confidence;
  final List<Prediction> top3;
  final AdvisoryBlock advisory;
  final String message;
  final String disclaimer;
  final String modelVersion;
  final String? gradcamBase64;
  final String? localImagePath;
  final String? imageUrl;

  const Diagnosis({
    this.serverId,
    required this.createdAt,
    required this.status,
    required this.level,
    required this.language,
    required this.cropKey,
    required this.cropName,
    required this.diseaseKey,
    required this.diseaseName,
    required this.confidence,
    required this.top3,
    required this.advisory,
    required this.message,
    required this.disclaimer,
    required this.modelVersion,
    this.gradcamBase64,
    this.localImagePath,
    this.imageUrl,
  });

  factory Diagnosis.fromJson(Map<String, dynamic> j) => Diagnosis(
        serverId: j['id'] as int?,
        createdAt: DateTime.tryParse(j['created_at'] as String? ?? '') ?? DateTime.now(),
        status: j['status'] as String? ?? 'unclear',
        level: j['level'] as String? ?? 'yellow',
        language: normalizeLang(j['language'] as String?),
        cropKey: j['crop_key'] as String? ?? '',
        cropName: j['crop_name'] as String? ?? '',
        diseaseKey: j['disease_key'] as String? ?? '',
        diseaseName: j['disease_name'] as String? ?? '',
        confidence: (j['confidence'] as num?)?.toDouble() ?? 0,
        top3: ((j['top3'] as List?) ?? [])
            .map((e) => Prediction.fromJson(Map<String, dynamic>.from(e as Map)))
            .toList(),
        advisory: AdvisoryBlock.fromJson(
            Map<String, dynamic>.from((j['advisory'] as Map?) ?? const {})),
        message: j['message'] as String? ?? '',
        disclaimer: j['disclaimer'] as String? ?? '',
        modelVersion: j['model_version'] as String? ?? '',
        gradcamBase64: j['gradcam_base64'] as String?,
        imageUrl: j['image_url'] as String?,
        localImagePath: j['local_image_path'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': serverId,
        'created_at': createdAt.toIso8601String(),
        'status': status,
        'level': level,
        'language': language,
        'crop_key': cropKey,
        'crop_name': cropName,
        'disease_key': diseaseKey,
        'disease_name': diseaseName,
        'confidence': confidence,
        'top3': top3.map((e) => e.toJson()).toList(),
        'advisory': advisory.toJson(),
        'message': message,
        'disclaimer': disclaimer,
        'model_version': modelVersion,
        'image_url': imageUrl,
        'local_image_path': localImagePath,
      };

  Diagnosis copyWith({String? localImagePath, String? gradcamBase64, int? serverId}) => Diagnosis(
        serverId: serverId ?? this.serverId,
        createdAt: createdAt,
        status: status,
        level: level,
        language: language,
        cropKey: cropKey,
        cropName: cropName,
        diseaseKey: diseaseKey,
        diseaseName: diseaseName,
        confidence: confidence,
        top3: top3,
        advisory: advisory,
        message: message,
        disclaimer: disclaimer,
        modelVersion: modelVersion,
        gradcamBase64: gradcamBase64 ?? this.gradcamBase64,
        localImagePath: localImagePath ?? this.localImagePath,
        imageUrl: imageUrl,
      );

  String get id => serverId?.toString() ?? '${createdAt.microsecondsSinceEpoch}';
}

class QueuedUpload {
  final String id;
  final String imagePath;
  final String language;
  final DateTime createdAt;

  const QueuedUpload({
    required this.id,
    required this.imagePath,
    required this.language,
    required this.createdAt,
  });

  factory QueuedUpload.fromJson(Map<String, dynamic> j) => QueuedUpload(
        id: j['id'] as String,
        imagePath: j['imagePath'] as String,
        language: normalizeLang(j['language'] as String?),
        createdAt: DateTime.tryParse(j['createdAt'] as String? ?? '') ?? DateTime.now(),
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'imagePath': imagePath,
        'language': language,
        'createdAt': createdAt.toIso8601String(),
      };
}

class WeatherAlert {
  final String level;
  final String icon;
  final String title;
  final String message;

  const WeatherAlert({
    required this.level,
    required this.icon,
    required this.title,
    required this.message,
  });

  factory WeatherAlert.fromJson(Map<String, dynamic> j) => WeatherAlert(
        level: j['level'] as String? ?? 'yellow',
        icon: j['icon'] as String? ?? 'cloud',
        title: j['title'] as String? ?? '',
        message: j['message'] as String? ?? '',
      );

  Map<String, dynamic> toJson() =>
      {'level': level, 'icon': icon, 'title': title, 'message': message};
}

class WeatherSnapshot {
  final double? temperature;
  final int? humidity;
  final double? rainfall;
  final double? wind;
  final int? rainTomorrow;
  final String condition;
  final List<WeatherAlert> alerts;
  final List<String> advice;
  final List<ForecastDay> days;
  final DateTime fetchedAt;

  const WeatherSnapshot({
    required this.temperature,
    required this.humidity,
    required this.rainfall,
    required this.wind,
    required this.rainTomorrow,
    required this.condition,
    required this.alerts,
    required this.advice,
    required this.days,
    required this.fetchedAt,
  });

  factory WeatherSnapshot.fromJson(Map<String, dynamic> j) {
    final cur = Map<String, dynamic>.from((j['current'] as Map?) ?? const {});
    return WeatherSnapshot(
      temperature: (cur['temperature_c'] as num?)?.toDouble(),
      humidity: (cur['humidity'] as num?)?.toInt(),
      rainfall: (cur['rainfall_mm'] as num?)?.toDouble(),
      wind: (cur['wind_kmh'] as num?)?.toDouble(),
      rainTomorrow: (cur['rain_probability_tomorrow'] as num?)?.toInt(),
      condition: cur['condition'] as String? ?? '',
      alerts: ((j['alerts'] as List?) ?? [])
          .map((e) => WeatherAlert.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList(),
      advice: ((j['advice'] as List?) ?? []).map((e) => e.toString()).toList(),
      days: ((j['days'] as List?) ?? [])
          .map((e) => ForecastDay.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList(),
      fetchedAt: DateTime.tryParse(j['fetched_at'] as String? ?? '') ?? DateTime.now(),
    );
  }

  /// Weather is cached by the app for offline use, so it must be serialisable.
  Map<String, dynamic> toJson() => {
        'current': {
          'temperature_c': temperature,
          'humidity': humidity,
          'rainfall_mm': rainfall,
          'wind_kmh': wind,
          'rain_probability_tomorrow': rainTomorrow,
          'condition': condition,
        },
        'alerts': alerts.map((e) => e.toJson()).toList(),
        'advice': advice,
        'days': days.map((e) => e.toJson()).toList(),
        'fetched_at': fetchedAt.toIso8601String(),
      };
}

class ForecastDay {
  final String date;
  final double? min;
  final double? max;
  final int? rainChance;
  final double? rainMm;
  final String condition;

  const ForecastDay({
    required this.date,
    required this.min,
    required this.max,
    required this.rainChance,
    required this.rainMm,
    required this.condition,
  });

  factory ForecastDay.fromJson(Map<String, dynamic> j) => ForecastDay(
        date: j['date'] as String? ?? '',
        min: (j['temp_min_c'] as num?)?.toDouble(),
        max: (j['temp_max_c'] as num?)?.toDouble(),
        rainChance: (j['rain_probability'] as num?)?.toInt(),
        rainMm: (j['rain_mm'] as num?)?.toDouble(),
        condition: j['condition'] as String? ?? '',
      );

  Map<String, dynamic> toJson() => {
        'date': date,
        'temp_min_c': min,
        'temp_max_c': max,
        'rain_probability': rainChance,
        'rain_mm': rainMm,
        'condition': condition,
      };
}

class AssistantAnswer {
  final String answer;
  final String language;
  final List<String> followUps;
  final String disclaimer;
  final List<String> sources;

  const AssistantAnswer({
    required this.answer,
    required this.language,
    required this.followUps,
    required this.disclaimer,
    required this.sources,
  });

  factory AssistantAnswer.fromJson(Map<String, dynamic> j) => AssistantAnswer(
        answer: j['answer'] as String? ?? '',
        language: normalizeLang(j['language'] as String?),
        followUps: ((j['follow_ups'] as List?) ?? []).map((e) => e.toString()).toList(),
        disclaimer: j['disclaimer'] as String? ?? '',
        sources: ((j['sources'] as List?) ?? [])
            .map((e) => (e as Map)['title']?.toString() ?? '')
            .where((e) => e.isNotEmpty)
            .toList(),
      );
}

String encodeList(List<Map<String, dynamic>> items) => jsonEncode(items);
