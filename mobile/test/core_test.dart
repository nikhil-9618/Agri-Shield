import 'package:agrishield/core/strings.dart';
import 'package:agrishield/models/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('all five languages carry the core farmer strings', () {
    const keys = [
      'appName',
      'checkCrop',
      'resultTitle',
      'sectionDoNow',
      'queuedBody',
      'voiceTitle',
      'weatherTitle',
      'helpCallOfficer',
    ];
    for (final lang in kLanguages) {
      for (final key in keys) {
        expect(
          L.t(lang, key),
          isNotEmpty,
          reason: 'missing $lang/$key',
        );
      }
    }
  });

  test('missing translation falls back to English', () {
    expect(L.t('te', 'a_key_that_does_not_exist'), 'a_key_that_does_not_exist');
    expect(L.t('xx', 'checkCrop'), L.t('en', 'checkCrop'));
  });

  test('diagnosis survives an offline JSON round trip', () {
    final diagnosis = Diagnosis(
      serverId: 7,
      createdAt: DateTime.utc(2026, 11, 16, 9, 30),
      status: 'diagnosed',
      level: 'red',
      language: 'te',
      cropKey: 'tomato',
      cropName: 'టమాటా',
      diseaseKey: 'tomato_late_blight',
      diseaseName: 'టమాటా ఆకు మచ్చ తెగులు',
      confidence: 0.91,
      top3: const [
        Prediction(
          key: 'tomato_late_blight',
          crop: 'tomato',
          disease: 'late_blight',
          confidence: 0.91,
          cropName: 'టమాటా',
          diseaseName: 'టమాటా ఆకు మచ్చ తెగులు',
          isHealthy: false,
        ),
      ],
      advisory: const AdvisoryBlock(
        name: 'టమాటా ఆకు మచ్చ తెగులు',
        signs: 'ఆకుపై నల్ల మచ్చలు',
        doNow: 'మచ్చల ఆకులు తీసి పక్కన పెట్టండి',
        avoid: 'తడిగా ఉన్నప్పుడు తాకవద్దు',
        prevention: 'గాలి తగిలేలా ఉంచండి',
        expert: 'మచ్చలు పెరిగితే అధికారిని కలవండి',
      ),
      message: 'తెగులు కనిపిస్తోంది',
      disclaimer: 'ఇది సూచన మాత్రమే',
      modelVersion: 'agrishield-mobilenetv2-v1',
      localImagePath: '/tmp/leaf.jpg',
    );

    final restored = Diagnosis.fromJson(diagnosis.toJson());
    expect(restored.serverId, 7);
    expect(restored.level, 'red');
    expect(restored.diseaseKey, 'tomato_late_blight');
    expect(restored.top3.single.confidence, closeTo(0.91, 0.001));
    expect(restored.advisory.doNow, isNotEmpty);
    expect(restored.localImagePath, '/tmp/leaf.jpg');
  });

  test('language keys are canonicalised', () {
    expect(normalizeLang('ta'), 'ta');
    expect(normalizeLang('kn'), 'kn');
    expect(normalizeLang('fr'), kDefaultLanguage);
    expect(normalizeLang(null), kDefaultLanguage);
  });
}
