import 'package:geolocator/geolocator.dart';

import '../models/models.dart';
import 'api_client.dart';

/// Thrown when the farmer has not granted (or enabled) location access.
class LocationUnavailable implements Exception {}

class WeatherUnavailable implements Exception {
  final String message;
  WeatherUnavailable(this.message);
}

/// Reads the phone's location and asks the backend for a weather snapshot.
/// Low accuracy is deliberate: a village-level forecast is all that is needed.
Future<WeatherSnapshot> loadWeatherForDevice(ApiClient api, String language) async {
  final serviceOn = await Geolocator.isLocationServiceEnabled();
  if (!serviceOn) throw LocationUnavailable();

  var permission = await Geolocator.checkPermission();
  if (permission == LocationPermission.denied) {
    permission = await Geolocator.requestPermission();
  }
  if (permission == LocationPermission.denied ||
      permission == LocationPermission.deniedForever) {
    throw LocationUnavailable();
  }

  Position? position;
  try {
    position = await Geolocator.getLastKnownPosition();
    position ??= await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.low,
        timeLimit: Duration(seconds: 20),
      ),
    );
  } catch (_) {
    throw WeatherUnavailable('location');
  }

  try {
    return await api.weather(position.latitude, position.longitude, language);
  } on ApiException catch (e) {
    throw WeatherUnavailable(e.status == 0 ? 'offline' : e.message);
  }
}
