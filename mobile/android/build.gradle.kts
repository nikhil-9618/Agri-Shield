allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
// tflite_flutter still declares Java 11 while the app and its Kotlin tasks use
// 17, which AGP 9 rejects as inconsistent. Compile the plugin at the same
// level; it has no Java-11-only requirements. Register before any subproject is
// evaluated (evaluationDependsOn below evaluates :app).
subprojects {
    afterEvaluate {
        extensions.findByType(com.android.build.gradle.LibraryExtension::class.java)?.apply {
            compileOptions {
                sourceCompatibility = JavaVersion.VERSION_17
                targetCompatibility = JavaVersion.VERSION_17
            }
        }
    }
}

// Some Flutter plugins (flutter_tts) still compile Kotlin to JVM 11 while AGP
// compiles their Java to 17. AGP 9 rejects that combination, so align every
// plugin's Kotlin target with the app before the build runs.
subprojects {
    tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>().configureEach {
        compilerOptions.jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

subprojects {
    project.evaluationDependsOn(":app")
}

// The Android Lint bundled with AGP 9 crashes on JDK 17's javadoc parser
// (NoSuchMethodError in JavaDocParser) while checking plugin modules. Lint is
// not part of producing the APK and Dart analysis covers our own code, so the
// lint tasks are disabled for every module including Flutter plugins.
subprojects {
    tasks.configureEach {
        if (name.startsWith("lint")) {
            enabled = false
        }
    }
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
