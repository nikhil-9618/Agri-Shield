import 'dart:math' as math;

import 'package:flutter/services.dart';
import 'package:google_mlkit_image_labeling/google_mlkit_image_labeling.dart';

/// Why a photo cannot be sent to the disease model.
enum LeafRejection {
  /// A person, face or skin is the main subject.
  person,

  /// There is no clear plant/leaf material in the frame.
  noLeaf,
}

class LeafGuardResult {
  final bool isLeaf;
  final LeafRejection? rejection;
  final double plantScore;
  final double personScore;
  final List<String> labels;

  const LeafGuardResult({
    required this.isLeaf,
    required this.rejection,
    required this.plantScore,
    required this.personScore,
    required this.labels,
  });
}

/// A technical failure while checking the photo. The caller must not fall back
/// to the disease model: an unchecked photo could be a person.
class LeafGuardException implements Exception {
  final String code;
  final String message;

  const LeafGuardException(this.code, this.message);

  @override
  String toString() => 'LeafGuardException($code: $message)';
}

/// On-device leaf/person gate powered by ML Kit's bundled image-labeling model.
///
/// This runs entirely on the phone: no API key, no request quota and no photo
/// leaves the device. It is deliberately strict. If ML Kit cannot decide, the
/// photo is refused rather than sent to the 27-class disease model, because
/// that model always returns a disease for any input.
class LeafGuard {
  /// ML Kit labels are only returned at or above this confidence.
  static const double labelThreshold = 0.25;

  /// A plant-related label at or above this score counts as leaf material.
  static const double plantThreshold = 0.30;

  /// A person/face label at or above this score rejects the photo.
  static const double personThreshold = 0.50;

  /// Close-up plant material. Scene labels such as "Forest", "Field" or
  /// "Garden" are intentionally excluded: a car in a field must not pass.
  static const Set<String> plantLabels = {
    'plant',
    'plants',
    'flora',
    'leaf',
    'leaves',
    'foliage',
    'twig',
    'branch',
    'seedling',
    'herb',
    'shrub',
  };

  /// People and body parts that should never reach a leaf diagnosis. "Hand" is
  /// excluded because farmers often hold the leaf while photographing it.
  static const Set<String> personLabels = {
    'person',
    'people',
    'selfie',
    'smile',
    'skin',
    'face',
    'human',
    'portrait',
    'baby',
    'crowd',
    'groom',
    'bride',
    'dude',
    'model',
    'mouth',
    'ear',
    'beard',
    'moustache',
  };

  ImageLabeler? _labeler;

  /// Pure decision logic, separated so it can be tested without a device.
  static LeafGuardResult evaluate(Map<String, double> scores) {
    final normalized = <String, double>{};
    for (final entry in scores.entries) {
      normalized[entry.key.trim().toLowerCase()] = entry.value;
    }

    double best(Set<String> names) {
      var value = 0.0;
      for (final name in names) {
        value = math.max(value, normalized[name] ?? 0.0);
      }
      return value;
    }

    final plantScore = best(plantLabels);
    final personScore = best(personLabels);
    final labels = normalized.entries.where((entry) => entry.value > 0).toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    if (personScore >= personThreshold) {
      return LeafGuardResult(
        isLeaf: false,
        rejection: LeafRejection.person,
        plantScore: plantScore,
        personScore: personScore,
        labels: labels.map((e) => '${e.key} ${e.value.toStringAsFixed(2)}').toList(),
      );
    }
    if (plantScore < plantThreshold) {
      return LeafGuardResult(
        isLeaf: false,
        rejection: LeafRejection.noLeaf,
        plantScore: plantScore,
        personScore: personScore,
        labels: labels.map((e) => '${e.key} ${e.value.toStringAsFixed(2)}').toList(),
      );
    }
    return LeafGuardResult(
      isLeaf: true,
      rejection: null,
      plantScore: plantScore,
      personScore: personScore,
      labels: labels.map((e) => '${e.key} ${e.value.toStringAsFixed(2)}').toList(),
    );
  }

  Future<LeafGuardResult> check(String path) async {
    try {
      final labeler = _labeler ??= ImageLabeler(
        options: ImageLabelerOptions(confidenceThreshold: labelThreshold),
      );
      final result = await labeler.processImage(InputImage.fromFilePath(path));
      final scores = <String, double>{};
      for (final label in result) {
        final key = label.label.trim().toLowerCase();
        if (key.isEmpty) continue;
        if ((scores[key] ?? 0) < label.confidence) {
          scores[key] = label.confidence;
        }
      }
      return evaluate(scores);
    } on PlatformException catch (e) {
      throw LeafGuardException(
        'leaf_check_unavailable',
        'The leaf check could not run: ${e.message ?? e.code}',
      );
    } catch (e) {
      throw LeafGuardException(
        'leaf_check_unavailable',
        'The leaf check could not run: $e',
      );
    }
  }

  Future<void> close() async {
    await _labeler?.close();
    _labeler = null;
  }
}
