# AgriShield mobile app

Flutter app for farmers with limited literacy. Big picture buttons, spoken
guidance in Telugu, Hindi, English, Tamil and Kannada, and no typing required.

## Run

```bash
# from the repo root
cd backend && ./run.sh              # API on :8000

cd mobile
flutter pub get
flutter run --dart-define=AGRI_API_BASE_URL=http://10.0.2.2:8000
```

`10.0.2.2` is the host machine as seen from the Android emulator. On a real
phone use the computer's LAN address, e.g.
`--dart-define=AGRI_API_BASE_URL=http://192.168.1.20:8000`. The server address
can also be changed at runtime in **Profile → Server address** (intended for
field helpers; the farmer never needs it).

The release APK is built with:

```bash
./scripts/build_apk.sh
```

and copied to `artifacts/agrishield-1.0.1-arm-release.apk`.

## What is in the app

| Screen | Purpose |
| --- | --- |
| Language | five language cards, each with a spoken sample |
| Welcome | three-picture explanation of how it works, read aloud |
| Home | four large actions: check crop, weather, past problems, help |
| Camera | framing guide and a single large shutter button |
| Analysis | upload/analyse/explain progress, queues the photo when offline |
| Result | green/yellow/red banner, confidence, top-3 guesses, heat map, spoken advisory |
| Voice | press the big mic and speak; answers come from the advisory knowledge base |
| Weather | current conditions, crop warnings, 7-day forecast; cached for offline |
| Alerts | warning list with spoken messages |
| History | saved diagnoses with photos, readable offline |
| Help | Kisan Call Centre 1800-180-1551 and how-to-use |
| Profile | name, village, language, server address |

## Offline behaviour

- The 27 disease advisories, crop names and messages are bundled assets, so any
  saved diagnosis stays readable with no network.
- A photo taken offline is copied into app storage and queued. When the server
  becomes reachable, the app uploads it and shows the result. It never shows a
  guessed result for an unsent photo.
- The last weather snapshot is cached and marked with its fetch time.
- With no connectivity the Voice screen reports that it cannot reach the server
  instead of inventing an answer.

## Data and privacy

An account is created silently on first launch with a random phone number and
random password stored only on the phone. There is no OTP, no form and no
password to remember. Photos are stored under the app's documents directory and
on the server under that account only.

## Checks

```bash
flutter analyze     # 0 issues
flutter test        # translation + offline JSON tests
```

No Android device or emulator was available in the build environment, so the APK
was compiled and statically analysed but not tapped through on a phone.
