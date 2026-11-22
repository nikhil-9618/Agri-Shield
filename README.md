
# 🌱 AgriShield
### Smart Crop Disease Detection & Agricultural Assistance

**Helping farmers identify crop diseases, understand symptoms, and take informed action — in their own language.**

AgriShield is an AI-powered Android application designed to make agricultural technology accessible to farmers across rural India.

Farmers can capture a picture of a crop leaf, receive an AI-based disease prediction, listen to agricultural guidance in their preferred language, and access weather-related warnings.

The application is designed for real-world conditions where internet connectivity may be unreliable, typing may be difficult, and English may not be familiar.

---

## 🌾 Why AgriShield?

Crop diseases can damage agricultural production when symptoms are not identified early.

Many farmers face challenges such as:
- Difficulty identifying plant diseases.
- Limited access to agricultural experts.
- Language barriers when using digital applications.
- Unreliable internet connectivity in rural areas.
- Confusing technical information about crop diseases.

**AgriShield aims to make crop health information simple, accessible, and understandable.**

---

## ✨ Key Features

### 1. 📸 AI-Powered Crop Disease Detection
- Capture a photograph of a crop leaf.
- Analyze the image using an on-device AI model.
- Receive a predicted disease or an unclear result.
- View prediction confidence.
- Access disease-specific agricultural guidance.

The application uses a MobileNetV2 model trained on the PlantVillage dataset.

**Important:** Predictions are research-model outputs, not confirmed field diagnoses. Accuracy on real-world field photographs has not yet been established.

### 2. 🗣️ Multilingual Voice Assistance

AgriShield supports five languages:

| Language | Availability |
|---|---|
| Telugu | Default |
| Hindi | Supported |
| English | Supported |
| Tamil | Supported |
| Kannada | Supported |

Features:
- Localized application screens.
- Spoken language guidance.
- Large speaker buttons.
- Simple explanations instead of complicated agricultural terminology.

### 3. 🌦️ Weather Information & Alerts
- Current weather information.
- Weather forecasts.
- Crop-related weather risk information.
- Cached weather information for offline reference.

Weather functionality requires an internet connection to retrieve updated information.

### 4. 🌱 Agricultural Disease Guidance

Each supported disease has a dedicated advisory containing:

- Common symptoms.
- Immediate actions.
- Things to avoid.
- Preventive practices.
- When to contact an agricultural expert.

The advisory content is available in five supported languages.

### 5. 📱 Offline-First Functionality

AgriShield is designed to work even when internet connectivity is unavailable.

Available offline:
- Crop disease model inference.
- Bundled agricultural advisories.
- Previously saved diagnosis results.
- Application language resources.
- Queued photo records for later synchronization.

Weather updates and server-dependent features require connectivity.

### 6. 🔊 Farmer-Friendly Interface

The application focuses on accessibility.

- Large buttons and readable text.
- Simple navigation.
- Colour-coded diagnosis results.
- Spoken instructions.
- Minimal typing.
- No mandatory registration for basic offline diagnosis.

---

## 🚦 Understanding Diagnosis Results

AgriShield uses three visual result categories.

| Colour | Meaning |
|---|---|
| 🟢 Green | No supported disease detected with sufficient confidence |
| 🟡 Yellow | Uncertain result; further inspection recommended |
| 🔴 Red | A supported disease prediction requires attention |

**Note:** A green result does not guarantee that a plant is disease-free. The model only recognizes the conditions represented by its supported classes.

---

## 🤖 AI Model & Performance

AgriShield uses transfer learning with MobileNetV2.

### Model Information

| Specification | Details |
|---|---|
| Architecture | MobileNetV2 |
| Training dataset | PlantVillage + PlantDoc (CC BY 4.0), 25,652 deduplicated images |
| Supported classes | 38 |
| Supported crop categories | 14 |
| Model format | TensorFlow Lite (float16) |
| Model size | 4.61 MB |
| Inference | On-device |
| Confidence calibration | Temperature scaling |
| Calibration temperature | 0.745 |

### Dataset Evaluation

Evaluated on 6,210 held-out images (5,991 PlantVillage + 219 PlantDoc field photos), with near-duplicate groups removed from the test split.

| Metric | Result |
|---|---:|
| Keras Top-1 Accuracy | 84.91% |
| Keras Macro F1 | 84.73% |
| TFLite Top-1 Accuracy | 86.22% |
| TFLite Top-3 Accuracy | 95.93% |
| Keras ↔ TFLite top-1 agreement | 99.75% (400 images) |

### Real-World Field Validation

PlantVillage images have controlled backgrounds and conditions. Real agricultural photographs contain different lighting, backgrounds, camera qualities, and disease stages.

On 236 independent PlantDoc field photos the model never trained on, top-1 is 38.1%. On 118 scorable Digital Green farmer photos it is 11.0%:

| Metric | Result |
|---|---:|
| Real field photographs evaluated | 118 |
| Top-1 agreement | 11.0% |
| Predictions rejected by calibrated confidence gate | 94.1% |
| Accuracy on the photos it did answer | 42.9% |
| Confident answers about a crop it does not know | 11.8% (of 626) |

**These results show that controlled-dataset accuracy cannot be treated as real-world agricultural accuracy.**

Improving field performance through representative agricultural datasets, expert-verified labels, and real-world testing is an important development priority.

Read the detailed reports:
- `docs/CALIBRATION.md`
- `docs/FIELD_VALIDATION.md`
- `docs/MODEL_CARD.md`

---

## 🏗️ Technology Stack

| Component | Technology |
|---|---|
| Android Application | Flutter |
| Programming Language | Dart |
| Backend API | Python, FastAPI |
| Database | SQLite / PostgreSQL |
| ORM | SQLAlchemy |
| Machine Learning | TensorFlow / Keras |
| Mobile Inference | TensorFlow Lite |
| Image Validation | Google ML Kit |
| Model Architecture | MobileNetV2 |
| API Communication | REST API |
| Deployment | Docker / Render |

---

## 📂 Project Structure

```text
AgriShield/
│
├── advisory/
│   ├── diseases/
│   ├── crops/
│   ├── messages/
│   ├── weather_rules/
│   └── assistant_faq.json
│
├── backend/
│   ├── API services
│   ├── ML inference
│   ├── Grad-CAM
│   └── tests
│
├── ml/
│   ├── training pipeline
│   ├── evaluation scripts
│   └── model artifacts
│
├── dataset/
│   └── dataset documentation
│
├── database/
│   ├── schema
│   └── initialization scripts
│
├── mobile/
│   ├── Flutter application
│   ├── screens
│   └── bundled assets
│
├── docs/
│   ├── API.md
│   ├── architecture
│   ├── accessibility
│   ├── testing
│   ├── deployment
│   └── model documentation
│
├── scripts/
│   ├── build scripts
│   └── setup scripts
│
└── README.md
```

---

## 🚀 Getting Started

Follow these instructions to run AgriShield locally.

### Prerequisites

Install the following tools:

- Flutter SDK
- Dart SDK
- Python 3.10 or compatible version specified by the backend dependencies
- Android Studio
- Android SDK
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/nikhil-9618/Agri-Shield.git
```

Navigate into the project:

```bash
cd Agri-Shield
```

### 2. Start the Backend

Run:

```bash
./backend/run.sh
```

The backend starts locally on:

```text
http://localhost:8000
```

Health check:

```text
http://localhost:8000/health
```

### 3. Start the Flutter Application

Navigate to the mobile directory:

```bash
cd mobile
```

Install dependencies:

```bash
flutter pub get
```

Run the application on an Android emulator:

```bash
flutter run --dart-define=AGRI_API_BASE_URL=http://10.0.2.2:8000
```

For a physical Android device, use your computer's reachable LAN IP address as the API base URL.

### 4. Build the Android APK

From the project root:

```bash
./scripts/build_apk.sh
```

The generated APK is placed in:

```text
artifacts/
```

---

## 📲 Android Application

AgriShield provides a universal Android APK.

| Specification | Details |
|---|---|
| Application | AgriShield |
| Package ID | org.agrishield.agrishield |
| Platform | Android |
| Minimum Android Version | Android 8.0 |
| Architecture | ARM64, ARMv7, x86_64 |
| Distribution | Universal APK |

### Download

[Download AgriShield Android APK – Version 1.4.3](https://github.com/nikhil-9618/Agri-Shield/releases/download/v1.4.3/agrishield-1.4.3-universal.apk)

Size: 58,902,009 bytes · SHA-256:
`dba967570c88a71a48efaa4dcc244ba1917cd9c4e807bb8ff284c7e75be4e5e3`

[View All Releases](https://github.com/nikhil-9618/Agri-Shield/releases)

---

## 🔌 Backend API

AgriShield uses a FastAPI backend for server-dependent functionality.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | API health check |
| POST | `/api/auth/register` | Register an account |
| POST | `/api/auth/login` | Authenticate a user |
| GET | `/api/auth/me` | Get authenticated user |
| GET / PUT | `/api/user/profile` | User profile |
| POST | `/api/detection/predict` | Server-side prediction |
| GET | `/api/detection/history` | Diagnosis history |
| GET | `/api/detection/{id}` | Diagnosis details |
| GET | `/api/detection/{id}/image` | Diagnosis image |
| GET | `/api/weather/current` | Current weather |
| GET | `/api/weather/forecast` | Weather forecast |
| GET | `/api/weather/risk` | Weather risk |
| GET | `/api/advisory/crops` | Supported crops |
| GET | `/api/advisory` | Agricultural advisories |
| GET | `/api/advisory/{disease}` | Disease-specific advisory |
| POST | `/api/assistant/ask` | Voice assistant query |

Detailed documentation:

`docs/API.md`

---

## 🔐 Privacy & Security

Farmer privacy is an important part of AgriShield.

- Basic offline diagnosis does not require an account.
- Image validation runs locally on the device.
- On-device disease inference does not require uploading the photograph.
- Server-dependent functionality is separated from offline diagnosis.
- Authentication is used for optional account-based services.
- No passwords, API keys, or signing credentials should be committed to the repository.

Photos may be uploaded when a user explicitly uses a server-dependent feature that requires image submission.

---

## 🧪 Testing & Verification

The following checks were recorded during the project's verification:

| Test | Result |
|---|---|
| Backend automated tests | 16 passed |
| Flutter static analysis | 0 issues |
| Flutter tests | 8 passed |
| TFLite model evaluation | Completed |
| Android APK build | Successful |
| APK installation on Android emulator | Successful |
| Render runtime tests | 10 passed |
| Docker image build | Not performed |
| Live Render deployment | Not performed |
| Physical device testing | Not performed |

For complete details, see:

`docs/TESTING.md`

---

## ⚠️ Important Limitations

AgriShield is an ongoing agricultural technology project.

Please understand these limitations:

1. The AI model is trained using PlantVillage, which does not fully represent real-world field conditions.
2. Real-world field accuracy has not been established.
3. The model cannot identify every possible crop disease.
4. Similar-looking diseases may produce incorrect predictions.
5. Weather information requires an internet connection for updates.
6. Agricultural recommendations should not replace professional diagnosis.
7. Farmers should consult qualified agricultural officers before making important crop-treatment decisions.

AgriShield does not currently provide pesticide brand recommendations or dosage instructions.

---

## 🛣️ Future Improvements

Planned areas of development include:

- Training with diverse, expert-verified Indian field photographs.
- Improving disease identification across different growth stages.
- Adding more regional crops and disease categories.
- Improving confidence calibration using independent field datasets.
- Building a larger agricultural knowledge base.
- Supporting additional Indian languages.
- Improving offline synchronization.
- Conducting field testing with farmers and agricultural experts.
- Evaluating model performance across different phones, cameras, and lighting conditions.

---

## 🤝 Contributing

Contributions are welcome!

You can contribute by:

- Improving Flutter application features.
- Developing and evaluating machine learning models.
- Adding verified agricultural information.
- Improving language translations.
- Reporting bugs.
- Improving documentation.
- Testing the application on real Android devices.

### Contribution Process

1. Fork this repository.
2. Create a new feature branch.
3. Make your changes.
4. Test your changes.
5. Submit a Pull Request with a clear description.

---

## 📜 License

Check the repository's `LICENSE` file for the applicable licensing terms.

---

## 🌱 Project Vision

**Technology should not be a barrier between farmers and agricultural knowledge.**

AgriShield aims to bring accessible crop health information, multilingual guidance, and AI-assisted agricultural support directly to farmers' smartphones.

Built with a farmer-first approach.

**AgriShield — Protecting Crops. Empowering Farmers.**
