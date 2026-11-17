# Advisory content: basis and maintenance

## What it is

`advisory/` is the app's farmer-facing knowledge base: 27 disease advisories plus
crop names, status messages, weather rules and the voice-assistant FAQ, each in
Telugu, Hindi, English, Tamil and Kannada.

Every disease file has the same shape:

```json
{
  "key": "tomato_late_blight",
  "crop": "tomato",
  "severity": "red",
  "is_healthy": false,
  "icon": "blight",
  "l": {
    "te": { "name": "...", "signs": "...", "do_now": "...", "avoid": "...",
            "prevention": "...", "expert": "..." },
    "hi": { ... }, "en": { ... }, "ta": { ... }, "kn": { ... }
  }
}
```

Severity distribution: **11 red**, **10 yellow**, **6 green** (the healthy
classes). The API maps a confident non-healthy prediction through this severity,
and the app colours the result from it.

## Where the content comes from

The advisories were written for this project from widely published extension
guidance for Indian farmers, including:

- ICAR crop protection and plant disease packages of practice;
- state agricultural university extension portals (e.g. TNAU Agritech Portal)
  and Krishi Vigyan Kendra material;
- the symptom descriptions published with PlantVillage for the same 27 classes;
- general integrated pest management (IPM) guidance: remove infected material,
  improve airflow, avoid overhead irrigation, rotate crops, sanitise tools.

They are **not** copied verbatim from a single copyrighted document, and they are
**not** a prescription.

## Safety rules followed

1. **No pesticide brand, active ingredient or dose.** The app tells the farmer
   what to look for, what cultural step to take now, what not to do, and when to
   involve an agriculture officer. Chemical choice is left to a qualified local
   adviser who knows the labelled product and local restrictions.
2. **No certainty.** "Signs look like…" rather than "your crop has…". Low model
   confidence produces an "unclear" result with a retake prompt.
3. **Healthy is also content.** Six healthy classes explain what to keep doing
   and what to watch for.
4. **Actionable, short sentences.** One idea per section, written for listening.
5. **Every result carries a disclaimer** and a prominent route to help (Kisan
   Call Centre 1800-180-1551 and the block agriculture officer).

## Language and translation

Telugu is the primary authored language; Hindi, English, Tamil and Kannada
follow the same structure. Translations use everyday spoken vocabulary and keep
local disease names. They have **not yet been reviewed by a professional
translator or a native agronomist**, so a pre-deployment review is strongly
recommended — start with the 11 red-severity diseases, where a mistranslation
matters most.

## Weather rules

`weather_rules.json` turns environmental conditions into farmer warnings
(rain soon, high humidity, heat stress, wind, dry spell, good weather). They are
deliberately about **conditions**, not diagnoses: high humidity raises blight
risk, it does not prove blight. Thresholds live in
`backend/app/services/weather.py` and are easy to tune for a region.

## Editing workflow

```bash
# 1. edit advisory/diseases/<key>.json or a shared file
python -m json.tool advisory/diseases/<key>.json > /dev/null

# 2. validate against the model classes and copy into the app bundle
./scripts/sync_advisory_assets.sh
cd backend && ../.venv/bin/python -m pytest tests -q

# 3. rebuild so the offline copy ships with the APK
./scripts/build_apk.sh
```

Rules:

- all 27 model keys must have exactly one file and all five languages;
- never rename a `key` without retraining/renaming in `class_names.json`;
- keep `severity` to `green`/`yellow`/`red`;
- the backend refuses to start if the advisory set and model classes disagree.

## Review needed before field use

- Agronomist review of all 27 advisories, especially red-severity ones and
  region-specific practices.
- Native-speaker review of the four non-Telugu translations.
- Add state-specific helpline numbers and KVK contacts rather than one national
  number for every farmer.
