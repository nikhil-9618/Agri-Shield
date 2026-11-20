import 'dart:convert';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/services.dart';
import 'package:tflite_flutter/tflite_flutter.dart';

import '../models/models.dart';

/// Thrown when the bundled model cannot run or the photo is unusable.
/// The caller can fall back to the server for everything except [invalid_image].
class OnDeviceException implements Exception {
  final String code;
  final String message;
  const OnDeviceException(this.code, this.message);

  @override
  String toString() => 'OnDeviceException($code: $message)';
}

class _ClassInfo {
  final int index;
  final String key;
  final String crop;
  final String disease;
  final bool healthy;

  const _ClassInfo({
    required this.index,
    required this.key,
    required this.crop,
    required this.disease,
    required this.healthy,
  });

  factory _ClassInfo.fromJson(Map<String, dynamic> j) => _ClassInfo(
        index: (j['index'] as num?)?.toInt() ?? 0,
        key: j['key'] as String? ?? '',
        crop: j['crop'] as String? ?? '',
        disease: j['disease'] as String? ?? '',
        healthy: j['is_healthy'] as bool? ?? false,
      );
}

/// Runs the trained MobileNetV2 TFLite model on the phone.
///
/// This is the same 27-class PlantVillage model the API serves, bundled with the
/// app. It makes a diagnosis work with no network at all; the server is still
/// used when the model is unavailable on an old device.
class OnDeviceClassifier {
  static const String modelAsset = 'assets/model/agrishield_model.tflite';
  static const String labelsAsset = 'assets/model/class_names.json';
  static const int inputSize = 128;

  /// Mirrors backend/app/config.py so on-device and server verdicts agree.
  static const double minConfidence = 0.55;
  static const double healthyConfidence = 0.60;

  Interpreter? _interpreter;
  List<_ClassInfo> _classes = const [];
  Map<String, dynamic> _messages = const {};
  Map<String, dynamic> _crops = const {};
  final Map<String, Map<String, dynamic>> _advisories = {};
  Future<void>? _loading;

  Future<void> ensureLoaded() => _loading ??= _load();

  Future<void> _load() async {
    try {
      _interpreter = await Interpreter.fromAsset(
        modelAsset,
        options: InterpreterOptions()..threads = 4,
      );
    } catch (_) {
      _loading = null;
      throw const OnDeviceException(
        'model_unavailable',
        'The on-device model could not be loaded.',
      );
    }

    final input = _interpreter!.getInputTensor(0).shape;
    final output = _interpreter!.getOutputTensor(0).shape;
    if (input.length != 4 ||
        input[1] != inputSize ||
        input[2] != inputSize ||
        input[3] != 3 ||
        output.isEmpty) {
      _loading = null;
      throw const OnDeviceException(
        'model_unavailable',
        'The bundled model has an unexpected shape.',
      );
    }

    final labels = jsonDecode(await rootBundle.loadString(labelsAsset)) as List;
    _classes = labels
        .map((e) => _ClassInfo.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
    if (_classes.length != output.last) {
      _loading = null;
      throw const OnDeviceException(
        'model_unavailable',
        'The model labels do not match the model output.',
      );
    }

    _messages = jsonDecode(await rootBundle.loadString('assets/advisory/messages.json'))
        as Map<String, dynamic>;
    _crops = jsonDecode(await rootBundle.loadString('assets/advisory/crops.json'))
        as Map<String, dynamic>;
  }

  /// Classifies a JPEG/PNG captured by the farmer. Throws [OnDeviceException]
  /// when the photo or model cannot be used; the caller then tries the API.
  Future<Diagnosis> classify(
    Uint8List bytes,
    String language, {
    String? localImagePath,
  }) async {
    final lang = normalizeLang(language);
    await ensureLoaded();

    final rgba = await _resize(bytes);
    final input = Float32List(inputSize * inputSize * 3);
    var sum = 0;
    for (var i = 0, p = 0; i < rgba.length; i += 4) {
      final r = rgba[i], g = rgba[i + 1], b = rgba[i + 2];
      sum += r + g + b;
      // The exported model scales 0-255 to [-1, 1] inside its own graph (the
      // training pipeline ends with mobilenet_v2.preprocess_input). Feeding
      // normalised pixels here would apply that twice and collapse every photo
      // onto one class.
      input[p++] = r.toDouble();
      input[p++] = g.toDouble();
      input[p++] = b.toDouble();
    }

    // A pitch-black frame is not a leaf; say so instead of guessing a disease.
    final brightness = sum / (inputSize * inputSize * 3);
    if (brightness < 18) {
      throw const OnDeviceException(
        'invalid_image',
        'The photo is too dark. Move to better light and try again.',
      );
    }

    final probs = Float32List(_classes.length);
    _interpreter!.run(input.buffer, probs.buffer);

    final order = List<int>.generate(probs.length, (i) => i)
      ..sort((a, b) => probs[b].compareTo(probs[a]));
    final top = _classes[order.first];
    final confidence = probs[order.first].clamp(0.0, 1.0);

    final block = await _advisory(top.key, lang);
    final severity = _severity(top.key);
    final top3 = <Prediction>[];
    for (final index in order.take(3)) {
      final info = _classes[index];
      final adv = await _advisory(info.key, lang);
      top3.add(Prediction(
        key: info.key,
        crop: info.crop,
        disease: info.disease,
        confidence: probs[index].clamp(0.0, 1.0),
        cropName: _cropName(info.crop, lang),
        diseaseName: (adv['name'] as String?) ?? info.key,
        isHealthy: info.healthy,
      ));
    }

    String status;
    String level;
    if (confidence < minConfidence) {
      status = 'unclear';
      level = 'yellow';
    } else if (top.healthy && confidence >= healthyConfidence) {
      status = 'diagnosed';
      level = 'green';
    } else {
      status = 'diagnosed';
      level = severity;
    }

    final message = status == 'unclear'
        ? _message('unclear', lang)
        : top.healthy
            ? _message('healthy', lang)
            : '${block['name'] ?? top.key}. ${block['signs'] ?? ''}'.trim();

    return Diagnosis(
      createdAt: DateTime.now(),
      status: status,
      level: level,
      language: lang,
      cropKey: top.crop,
      cropName: _cropName(top.crop, lang),
      diseaseKey: top.key,
      diseaseName: (block['name'] as String?) ?? top.key,
      confidence: confidence,
      top3: top3,
      advisory: AdvisoryBlock.fromJson(block),
      message: message,
      disclaimer: _message('disclaimer', lang),
      modelVersion: 'agrishield-mobilenetv2-tflite-ondevice',
      localImagePath: localImagePath,
    );
  }

  Future<Uint8List> _resize(Uint8List bytes) async {
    ui.Codec codec;
    try {
      codec = await ui.instantiateImageCodec(bytes);
    } catch (_) {
      throw const OnDeviceException(
        'invalid_image',
        'This file is not a readable JPEG or PNG photo.',
      );
    }
    final frame = await codec.getNextFrame();
    final image = frame.image;
    if (image.width < 80 || image.height < 80) {
      image.dispose();
      codec.dispose();
      throw const OnDeviceException(
        'invalid_image',
        'The photo is too small. Move closer to the leaf and try again.',
      );
    }

    final recorder = ui.PictureRecorder();
    final canvas = ui.Canvas(recorder);
    canvas.drawImageRect(
      image,
      ui.Rect.fromLTWH(0, 0, image.width.toDouble(), image.height.toDouble()),
      ui.Rect.fromLTWH(0, 0, inputSize.toDouble(), inputSize.toDouble()),
      ui.Paint()..filterQuality = ui.FilterQuality.medium,
    );
    final picture = recorder.endRecording();
    final resized = await picture.toImage(inputSize, inputSize);
    final data = await resized.toByteData(format: ui.ImageByteFormat.rawRgba);
    image.dispose();
    codec.dispose();
    picture.dispose();
    resized.dispose();

    if (data == null) {
      throw const OnDeviceException('invalid_image', 'The photo could not be read.');
    }
    return data.buffer.asUint8List();
  }

  Future<Map<String, dynamic>> _advisory(String key, String lang) async {
    final doc = _advisories[key] ?? await _loadAdvisory(key);
    final blocks = (doc['l'] as Map?) ?? const {};
    return Map<String, dynamic>.from((blocks[lang] ?? blocks['en'] ?? const {}) as Map);
  }

  String _severity(String key) {
    final value = _advisories[key]?['severity'];
    return value == 'green' || value == 'red' ? value as String : 'yellow';
  }

  Future<Map<String, dynamic>> _loadAdvisory(String key) async {
    try {
      final raw = await rootBundle.loadString('assets/advisory/diseases/$key.json');
      final doc = jsonDecode(raw) as Map<String, dynamic>;
      _advisories[key] = doc;
      return doc;
    } catch (_) {
      final empty = <String, dynamic>{'l': <String, dynamic>{}};
      _advisories[key] = empty;
      return empty;
    }
  }

  String _cropName(String crop, String lang) {
    final item = _crops[crop];
    final names = item is Map ? item['names'] : null;
    if (names is Map) {
      final value = names[lang] ?? names['en'];
      if (value != null) return value.toString();
    }
    return crop;
  }

  String _message(String key, String lang) {
    final item = _messages[key];
    if (item is Map) {
      final value = item[lang] ?? item['en'];
      if (value != null) return value.toString();
    }
    return '';
  }
}
