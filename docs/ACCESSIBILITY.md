# Accessibility and farmer-first design

The primary user reads slowly, may not read English, works outdoors in bright
sun, and may be new to smartphones. The app is designed around those constraints
rather than around a standard Material demo.

## Rules applied

| Rule | Implementation |
| --- | --- |
| No typing to use the app | account created silently; voice input; prepared question chips; only optional profile fields use a keyboard |
| Large touch targets | primary buttons 68 dp high; home tiles ≥ 110 dp; mic button 168 dp; shutter 104 dp |
| Large type | body 18–20 sp, headings 21–32 sp; system font scaling clamped to 0.9–1.3 so layouts never break |
| Icons + words + colour | every state has an icon, a sentence and a colour, never colour alone |
| Traffic-light result | green = healthy, yellow = attention/unclear, red = disease signs, each with a symbol and localised heading |
| Audio everywhere | speaker button on home, welcome, camera guide, result, each advisory section, each alert, voice answers, weather header |
| Local language first | Telugu default, then Hindi, English, Tamil, Kannada; language names printed in their own script and spoken on tap |
| No false certainty | low-confidence results show "unclear", missing data is shown as `--`, offline states say so instead of inventing content |
| Works without network | bundled advisories, saved results, photo queue, cached weather |
| Minimal navigation depth | home → camera → result is two taps; bottom bar keeps four destinations |
| Clear errors | plain sentences with a retry button; permission failures explain what to enable |

## Screen-reader and semantics

Interactive tiles and the mic carry `Semantics` labels that combine title and
subtitle, the language cards expose `selected`, and the mic announces
"listening"/"tap to speak". Text is real selectable text (not images), so Android
TalkBack can read every screen.

## Voice

- TTS: `flutter_tts` at 0.45 rate for clarity, language-specific locales
  (`te-IN`, `hi-IN`, `en-IN`, `ta-IN`, `kn-IN`). If a device lacks a voice the
  app still shows the text and says so once.
- STT: `speech_to_text` with partial results; on permission denial or missing
  recogniser the app shows prepared questions the farmer can tap instead.
- Results and answers are spoken automatically once, with a replay button.

## Language quality

The five UI languages are written in everyday spoken style, not technical
agronomy terms (e.g. "leaf spots" rather than "lesions"). Disease names keep the
local common name. Numbers, temperatures and percentages use Latin digits, which
are widely read.

## Known gaps

- No formal WCAG/TalkBack audit was run, and no farmer usability test was
  possible in this environment.
- Font sizes were chosen by inspection; a field test with elderly users and
  cheap 5-inch screens should confirm them.
- Some explanations (e.g. server address in Profile) remain English-only and are
  intended for field helpers, not farmers.
- Speech recognition quality for Telugu/Tamil/Kannada depends on the phone's
  Google speech service and language pack; without the pack, tapping prepared
  questions still works.

## Recommended next usability test

With 5–8 farmers who cannot read English: can they start a check without help,
understand a red vs green result, find the speaker button, and recover from an
offline check? Watch for hesitation at the language screen and the camera guide.
