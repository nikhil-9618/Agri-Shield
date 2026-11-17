import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_to_text.dart';

/// Voice is the primary interface, so both directions degrade gracefully:
/// if a language voice is missing we still show text, and if speech
/// recognition is unavailable the farmer can tap a prepared question.
class SpeechService {
  final FlutterTts _tts = FlutterTts();
  final SpeechToText _stt = SpeechToText();

  bool _ttsReady = false;
  bool _ttsAvailable = true;
  bool _sttInitialised = false;
  bool _listening = false;
  void Function(String)? _errorHandler;

  static const Map<String, String> ttsLocales = {
    'te': 'te-IN',
    'hi': 'hi-IN',
    'en': 'en-IN',
    'ta': 'ta-IN',
    'kn': 'kn-IN',
  };

  static const Map<String, String> sttLocales = {
    'te': 'te_IN',
    'hi': 'hi_IN',
    'en': 'en_IN',
    'ta': 'ta_IN',
    'kn': 'kn_IN',
  };

  bool get isListening => _listening;

  Future<void> _initTts() async {
    if (_ttsReady) return;
    try {
      await _tts.setSpeechRate(0.45); // slower, clearer for elderly farmers
      await _tts.setVolume(1.0);
      await _tts.setPitch(1.0);
      await _tts.awaitSpeakCompletion(true);
      _ttsReady = true;
    } catch (_) {
      _ttsAvailable = false;
    }
  }

  /// Returns false when the device has no TTS engine.
  Future<bool> speak(String text, String language) async {
    if (text.trim().isEmpty) return false;
    await _initTts();
    if (!_ttsAvailable) return false;
    try {
      await _tts.setLanguage(ttsLocales[language] ?? 'en-IN');
      await _tts.stop();
      await _tts.speak(text);
      return true;
    } catch (_) {
      try {
        await _tts.setLanguage('en-IN');
        await _tts.speak(text);
        return true;
      } catch (_) {
        return false;
      }
    }
  }

  Future<void> stop() async {
    try {
      await _tts.stop();
    } catch (_) {}
  }

  Future<bool> initSpeechRecognition() async {
    if (_sttInitialised) return true;
    try {
      _sttInitialised = await _stt.initialize(
        onError: (error) => _errorHandler?.call(error.errorMsg),
        onStatus: (status) {
          if (status == 'done' || status == 'notListening') _listening = false;
        },
      );
    } catch (_) {
      _sttInitialised = false;
    }
    return _sttInitialised;
  }

  Future<bool> listen({
    required String language,
    required void Function(String text, bool isFinal) onResult,
    required void Function(String error) onError,
  }) async {
    final ready = await initSpeechRecognition();
    if (!ready) {
      onError('unavailable');
      return false;
    }
    _errorHandler = onError;
    try {
      await _stt.listen(
        onResult: (result) => onResult(result.recognizedWords, result.finalResult),
        listenOptions: SpeechListenOptions(
          localeId: sttLocales[language] ?? 'en_IN',
          listenMode: ListenMode.confirmation,
          partialResults: true,
          cancelOnError: true,
          listenFor: const Duration(seconds: 25),
          pauseFor: const Duration(seconds: 3),
        ),
      );
      _listening = true;
      return true;
    } catch (e) {
      onError('$e');
      return false;
    }
  }

  Future<void> stopListening() async {
    _listening = false;
    try {
      await _stt.stop();
    } catch (_) {}
  }
}
