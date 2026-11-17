# API reference

Base URL in development: `http://localhost:8000`. Interactive docs:
`/docs` (Swagger) and `/redoc`.

All endpoints except `/health` require a bearer token:

```
Authorization: Bearer <access_token>
```

`lang` is one of `te`, `hi`, `en`, `ta`, `kn`. When omitted, the language stored
on the account is used. Wrong or missing languages fall back to Telugu.

Errors use FastAPI's shape, with a machine code and a message already translated
into the requested language:

```json
{ "detail": { "code": "invalid_image", "message": "ఫోటో సరిగ్గా లేదు..." } }
```

Status codes used: `400` (bad request), `401` (bad/expired token), `404`
(not found or not yours), `422` (validation / unreadable image), `429` (rate
limit), `503` (model not loaded).

Rate limit: 60 requests/minute per client IP (`RATE_LIMIT_PER_MINUTE`).
Upload limit: 8 MB (`MAX_UPLOAD_MB`). Security headers are added to every
response; CORS origins come from `CORS_ORIGINS`.

## Meta

### `GET /health`

```json
{ "status": "ok", "model_loaded": true, "model_version": "agrishield-mobilenetv2-v1",
  "classes": 27, "advisory_loaded": true }
```

## Authentication

Accounts are normally created by the app itself with a random phone number and
password, but the API is a normal phone/password API.

### `POST /api/auth/register`

```json
{ "phone": "9876543210", "name": "Farmer", "password": "secret123", "language": "te" }
```

`201` with:

```json
{ "access_token": "eyJ...", "token_type": "bearer",
  "user": { "id": 1, "phone": "9876543210", "name": "Farmer", "language": "te",
            "village": null, "state": null, "created_at": "2026-11-16T09:00:00Z" } }
```

`400` if the phone is already registered. Phone: 10–15 digits, digits only.

### `POST /api/auth/login`

```json
{ "phone": "9876543210", "password": "secret123" }
```

Returns the same token envelope. `401` for wrong credentials.

### `GET /api/auth/me`

Returns the user object.

## Profile

### `GET /api/user/profile`

### `PUT /api/user/profile`

Any subset of:

```json
{ "name": "Ramesh", "village": "Kothapalli", "language": "te", "password": "newsecret" }
```

Returns the updated user object.

## Detection

### `POST /api/detection/predict?lang=te`

`multipart/form-data` with one field `file` (JPEG/PNG/WebP). The server strips
EXIF/GPS and stores a resized copy.

`200`:

```json
{
  "id": 42,
  "created_at": "2026-11-16T09:12:00Z",
  "status": "diagnosed",
  "level": "red",
  "language": "te",
  "crop_key": "tomato",
  "crop_name": "టమాటా",
  "disease_key": "tomato_late_blight",
  "disease_name": "టమాటా ఆకు మచ్చ తెగులు",
  "confidence": 0.91,
  "top3": [
    { "key": "tomato_late_blight", "crop": "tomato", "disease": "late_blight",
      "confidence": 0.91, "crop_name": "టమాటా", "disease_name": "...", "is_healthy": false }
  ],
  "advisory": { "name": "...", "signs": "...", "do_now": "...", "avoid": "...",
                "prevention": "...", "expert": "..." },
  "gradcam_base64": "iVBORw0...",
  "message": "తెగులు కనిపిస్తోంది",
  "disclaimer": "ఇది AI సూచన మాత్రమే...",
  "model_version": "agrishield-mobilenetv2-v1",
  "image_url": "/api/detection/42/image"
}
```

Decision rules (server-side, in this order):

| Condition | `status` | `level` |
| --- | --- | --- |
| top confidence < `MIN_CONFIDENCE` (0.55) | `unclear` | `yellow` |
| healthy class and confidence >= `HEALTHY_CONFIDENCE` (0.60) | `diagnosed` | `green` |
| otherwise | `diagnosed` | red/yellow from the disease advisory severity |

`gradcam_base64` is `null` when Grad-CAM is disabled (`GRADCAM_ENABLED=false`)
or the Keras model is unavailable. The app then hides the heat-map button.

`422 invalid_image` for corrupt/unsupported/oversized images, `503
model_unavailable` when the TFLite model is missing or failed to load.

### `GET /api/detection/history?lang=te&limit=50`

```json
{ "total": 1, "items": [ { "id": 42, "created_at": "...", "crop_key": "tomato",
  "crop_name": "టమాటా", "disease_key": "tomato_late_blight", "disease_name": "...",
  "confidence": 0.91, "level": "red", "status": "diagnosed",
  "image_url": "/api/detection/42/image" } ] }
```

Newest first, limited to 200. Only the caller's own detections.

### `GET /api/detection/{id}?lang=te`

Full detection object, including the advisory in the requested language. `404`
for another user's detection (ownership is enforced, not just hidden).

### `GET /api/detection/{id}/image`

Returns the stored JPEG. Requires the owner's token.

## Weather

Open-Meteo is queried with a 10-minute cache (`WEATHER_CACHE_SECONDS`). Weather
is fact; crop warnings are environmental conditions, never a disease diagnosis.

### `GET /api/weather/current?lat=17.4&lon=78.5&lang=te`

```json
{
  "location": { "latitude": 17.4, "longitude": 78.5, "timezone": "Asia/Kolkata", "elevation": 545 },
  "current": { "temperature_c": 29.4, "humidity": 78, "rainfall_mm": 0.0,
               "wind_kmh": 8.2, "weather_code": 2, "condition": "మేఘావృతం",
               "rain_probability_tomorrow": 62 },
  "alerts": [ { "level": "yellow", "icon": "umbrella", "title": "రేపు వర్షం",
                "message": "..." } ],
  "advice": ["..."],
  "fetched_at": "2026-11-16T09:10:00Z",
  "source": "Open-Meteo"
}
```

### `GET /api/weather/forecast?lat=&lon=&lang=`

`days` is up to 7 entries with `date`, `temp_min_c`, `temp_max_c`,
`rain_probability`, `rain_mm`, `condition`, plus the same `alerts`/`advice`.

### `GET /api/weather/risk?lat=&lon=&lang=&crop=tomato`

Per-crop environmental risk with `level`, `title`, `message` and `reasons`.

## Advisory

### `GET /api/advisory/crops`

Crop list with localised names.

### `GET /api/advisory`

All 27 diseases: key, crop, localised name, severity level, healthy flag.

### `GET /api/advisory/{disease}`

One localised advisory block: `name`, `signs`, `do_now`, `avoid`, `prevention`,
`expert`. Also included in every detection response.

## Assistant

### `POST /api/assistant/ask`

```json
{ "question": "నా ఆకు పసుపు రంగులో ఉంది, ఏం చేయాలి?",
  "language": "te", "latitude": 17.4, "longitude": 78.5 }
```

```json
{ "answer": "…", "language": "te",
  "sources": [ { "title": "టమాటా ఆకు మచ్చ తెగులు", "reference": "advisory/tomato_late_blight" } ],
  "follow_ups": ["…"],
  "disclaimer": "ఇది సూచన మాత్రమే…" }
```

Retrieval only: the service matches the question against the bundled FAQ,
disease signs and advisories, and — when coordinates are supplied — current
weather. Unknown questions get a fallback that points to the agriculture officer;
the service never invents pesticide doses or a diagnosis.
