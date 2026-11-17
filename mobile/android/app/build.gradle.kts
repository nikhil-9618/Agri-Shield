import java.io.FileInputStream
import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
if (keystorePropertiesFile.exists()) {
    keystoreProperties.load(FileInputStream(keystorePropertiesFile))
}

android {
    namespace = "org.agrishield.agrishield"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "org.agrishield.agrishield"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        // Flutter 3.50 supports Android 7.0+ (API 24). The APK is universal
        // (arm64-v8a, armeabi-v7a, x86_64) and signed with v2+v3.
        minSdk = flutter.minSdkVersion
        // 34 installs on the widest range of OEM package installers; the app
        // does not use any API-35/36-only behaviour.
        targetSdk = 34
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (keystorePropertiesFile.exists()) {
            create("release") {
                keyAlias = keystoreProperties["keyAlias"] as String
                keyPassword = keystoreProperties["keyPassword"] as String
                storeFile = file(keystoreProperties["storeFile"] as String)
                storePassword = keystoreProperties["storePassword"] as String
                // Old and picky installers expect the JAR signature; modern
                // Android wants v2/v3. Ship all three.
                enableV1Signing = true
                enableV2Signing = true
                enableV3Signing = true
            }
        }
    }

    packaging {
        // Extract native libraries at install time. Slightly larger on disk,
        // but avoids install failures on devices with unusual page sizes or
        // package installers that reject uncompressed libraries.
        jniLibs {
            useLegacyPackaging = true
        }
    }

    lint {
        // Android Lint's bundled javadoc parser crashes on this JDK, and lint
        // is not part of producing the APK. Dart analysis covers the app code.
        checkReleaseBuilds = false
        abortOnError = false
    }

    buildTypes {
        release {
            // Uses android/key.properties when present (see documentation/DEPLOYMENT.md);
            // falls back to the debug key so a release APK can always be produced.
            signingConfig = if (keystorePropertiesFile.exists()) {
                signingConfigs.getByName("release")
            } else {
                signingConfigs.getByName("debug")
            }
            isMinifyEnabled = false
            // AGP 9 enables resource shrinking by default; it requires code
            // shrinking, which we deliberately keep off so the APK is simple.
            isShrinkResources = false
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
