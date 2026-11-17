import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../models/models.dart';

class ApiException implements Exception {
  final String code;
  final String message;
  final int status;

  ApiException(this.code, this.message, this.status);

  bool get isAuthError => status == 401;
  bool get isOffline => status == 0;

  @override
  String toString() => 'ApiException($status, $code: $message)';
}

class AuthResult {
  final String token;
  final UserProfile user;
  final String? phone;
  final String? password;
  const AuthResult({
    required this.token,
    required this.user,
    this.phone,
    this.password,
  });
}

class ApiClient {
  ApiClient({required this.baseUrl, required this.tokenProvider});

  final String baseUrl;
  final String? Function() tokenProvider;

  Uri _uri(String path, [Map<String, String>? query]) {
    final clean = path.startsWith('/') ? path.substring(1) : path;
    final root = baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl;
    return Uri.parse('$root/$clean').replace(queryParameters: query);
  }

  Map<String, String> get _headers {
    final token = tokenProvider();
    return {
      'Accept': 'application/json',
      if (token != null && token.isNotEmpty) 'Authorization': 'Bearer $token',
    };
  }

  Future<Map<String, dynamic>> _decode(http.Response response) async {
    Map<String, dynamic> body = {};
    if (response.body.isNotEmpty) {
      try {
        final decoded = jsonDecode(response.body);
        if (decoded is Map<String, dynamic>) body = decoded;
      } catch (_) {
        // non-JSON error body
      }
    }
    if (response.statusCode >= 200 && response.statusCode < 300) return body;

    final detail = body['detail'];
    String code = 'http_${response.statusCode}';
    String message = '';
    if (detail is Map) {
      code = detail['code']?.toString() ?? code;
      message = detail['message']?.toString() ?? '';
    } else if (detail is String) {
      message = detail;
    }
    if (message.isEmpty) message = 'Server error (${response.statusCode})';
    throw ApiException(code, message, response.statusCode);
  }

  Future<Map<String, dynamic>> _get(String path, [Map<String, String>? query]) async {
    try {
      final res = await http
          .get(_uri(path, query), headers: _headers)
          .timeout(const Duration(seconds: 20));
      return await _decode(res);
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException('network_error', 'Could not reach the server.', 0);
    }
  }

  Future<Map<String, dynamic>> _send(
    String method,
    String path,
    Map<String, dynamic> data, {
    Map<String, String>? query,
  }) async {
    try {
      final body = jsonEncode(data);
      final uri = _uri(path, query);
      final headers = {..._headers, 'Content-Type': 'application/json'};
      final res = method == 'POST'
          ? await http.post(uri, headers: headers, body: body).timeout(const Duration(seconds: 25))
          : await http.put(uri, headers: headers, body: body).timeout(const Duration(seconds: 25));
      return await _decode(res);
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException('network_error', 'Could not reach the server.', 0);
    }
  }

  // ------------------------------------------------------------------- auth
  static String _randomDigits(int count) {
    final rnd = Random.secure();
    return List.generate(count, (_) => rnd.nextInt(10)).join();
  }

  /// Creates a no-typing, no-phone-number account. The generated credentials are
  /// stored only on this phone so the farmer can be signed back in automatically.
  Future<AuthResult> registerAccount({required String language, required String password}) async {
    final phone = '9${_randomDigits(9)}';
    final body = await _send('POST', '/api/auth/register', {
      'phone': phone,
      'name': 'Farmer',
      'password': password,
      'language': language,
    });
    return AuthResult(
      token: body['access_token'] as String,
      user: UserProfile.fromJson(Map<String, dynamic>.from(body['user'] as Map)),
      phone: phone,
      password: password,
    );
  }

  Future<AuthResult> login({required String phone, required String password}) async {
    final body = await _send('POST', '/api/auth/login', {'phone': phone, 'password': password});
    return AuthResult(
      token: body['access_token'] as String,
      user: UserProfile.fromJson(Map<String, dynamic>.from(body['user'] as Map)),
    );
  }

  Future<UserProfile> me() async =>
      UserProfile.fromJson(await _get('/api/auth/me'));

  Future<UserProfile> updateProfile(Map<String, dynamic> changes) async =>
      UserProfile.fromJson(await _send('PUT', '/api/user/profile', changes));

  // -------------------------------------------------------------- detection
  Future<Diagnosis> predict(Uint8List bytes, String filename, String language) async {
    try {
      final request = http.MultipartRequest(
        'POST',
        _uri('/api/detection/predict', {'lang': language}),
      );
      final token = tokenProvider();
      if (token != null && token.isNotEmpty) {
        request.headers['Authorization'] = 'Bearer $token';
      }
      request.files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename));
      final streamed = await request.send().timeout(const Duration(seconds: 45));
      final response = await http.Response.fromStream(streamed);
      final body = await _decode(response);
      return Diagnosis.fromJson(body);
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException('network_error', 'Could not reach the server.', 0);
    }
  }

  Future<Diagnosis> getDetection(int id, String language) async =>
      Diagnosis.fromJson(await _get('/api/detection/$id', {'lang': language}));

  Future<List<Diagnosis>> history(String language, {int limit = 50}) async {
    final body = await _get('/api/detection/history', {
      'lang': language,
      'limit': '$limit',
    });
    return ((body['items'] as List?) ?? [])
        .map((e) => Diagnosis.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  // ----------------------------------------------------------------- weather
  Future<WeatherSnapshot> weather(double lat, double lon, String language) async {
    final q = {'lat': '$lat', 'lon': '$lon', 'lang': language};
    final current = await _get('/api/weather/current', q);
    final forecast = await _get('/api/weather/forecast', q);
    return WeatherSnapshot.fromJson({
      ...current,
      'days': forecast['days'],
      'alerts': current['alerts'],
      'advice': current['advice'],
    });
  }

  Future<List<String>> cropRisk(double lat, double lon, String language) async {
    final body = await _get('/api/weather/risk', {'lat': '$lat', 'lon': '$lon', 'lang': language});
    final risks = (body['risks'] as List?) ?? [];
    return risks
        .map((r) => '${(r as Map)['title']}: ${r['message']}')
        .map((s) => s.toString())
        .toList();
  }

  // --------------------------------------------------------------- assistant
  Future<AssistantAnswer> ask(
    String question,
    String language, {
    double? latitude,
    double? longitude,
  }) async {
    final body = await _send('POST', '/api/assistant/ask', {
      'question': question,
      'language': language,
      'latitude': ?latitude,
      'longitude': ?longitude,
    });
    return AssistantAnswer.fromJson(body);
  }

  // ----------------------------------------------------------------- advisory
  Future<Map<String, dynamic>> advisory(String diseaseKey, String language) async =>
      _get('/api/advisory/$diseaseKey', {'lang': language});

  Future<bool> health() async {
    try {
      final body = await _get('/health');
      return body['status'] == 'ok' && body['model_loaded'] == true;
    } catch (_) {
      return false;
    }
  }

  String absoluteImage(String? path) {
    if (path == null || path.isEmpty) return '';
    if (path.startsWith('http')) return path;
    final root = baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl;
    return '$root$path';
  }
}
