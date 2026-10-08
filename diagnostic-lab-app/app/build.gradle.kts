plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.google.devtools.ksp")
    id("com.google.gms.google-services")
}

android {
    namespace = "com.digitalsolutions.diagnosticlab"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.digitalsolutions.diagnosticlab"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0-mvp"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        // Set only by the CI workflow (-Pci=true), never by a developer's own build — a
        // device-fingerprint heuristic for "is this an emulator" turned out to be too fragile
        // (GitHub's own google_apis emulator image didn't match any of its checks, silently
        // re-enabling Play Integrity there and bringing back the RecaptchaActivity-steals-focus
        // bug the check exists to avoid). This flag is deterministic instead: it's true exactly
        // when the CI workflow itself set it, nothing to guess.
        buildConfigField("boolean", "IS_CI", (project.findProperty("ci") == "true").toString())

        // Maps SDK keys are safe to compile into the client (unlike Razorpay's secret) — their
        // security model is API/package/SHA-1 restriction on the Google Cloud Console side, not
        // secrecy. Still never hardcoded here: read from a Gradle property so local devs pass
        // -PMAPS_API_KEY=... and CI reads it from a repository secret, matching the -Pci=true
        // pattern above. Left blank, the manifest's meta-data value is an empty string — Maps
        // SDK then fails at runtime with a clear "no API key" error rather than a confusing one,
        // and the app still compiles fine either way (this value never affects compilation).
        manifestPlaceholders["MAPS_API_KEY"] = (project.findProperty("MAPS_API_KEY") as String?).orEmpty()
    }

    // Firebase Phone Auth's Play Integrity/reCAPTCHA verification needs the app's signing
    // certificate fingerprint registered in Firebase Console — but the Android Gradle Plugin's
    // default debug signing config uses whatever debug.keystore already exists on the machine,
    // generating a brand-new one if it doesn't. On GitHub Actions that's a fresh, different
    // keystore on every single run (the runner is thrown away each time), so a fingerprint
    // registered today goes stale on the next build. A committed, stable debug keystore fixes
    // this: register its fingerprint once, and every future CI and local debug build shares it.
    // Safe to commit — unlike a release keystore, a debug keystore can never sign a build
    // distributable via Play Store, so there's nothing sensitive in it.
    signingConfigs {
        getByName("debug") {
            storeFile = file("keystore/debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
        // The real Play Store signing key — deliberately NOT a file in this repo (contrast the
        // committed debug.keystore above). Only ever supplied as env vars: locally, a developer
        // exports them in their own shell before running a release build; in CI, the release
        // workflow decodes the RELEASE_KEYSTORE_BASE64 GitHub Actions secret to a temp file and
        // sets these same three env vars from the matching secrets. All three are null on any
        // ordinary build (debug builds, PR checks), which is why the release buildType below
        // only attaches this config when a keystore path is actually present — a release build
        // attempted without it fails fast with a clear Gradle error instead of silently trying
        // to sign with nothing.
        create("release") {
            val keystorePath = System.getenv("RELEASE_KEYSTORE_PATH")
            if (keystorePath != null) {
                storeFile = file(keystorePath)
                storePassword = System.getenv("RELEASE_KEYSTORE_PASSWORD")
                // PKCS12 (what this project's release keystore is) only supports one password
                // for both the store and the key entry — keytool silently ignores a second one
                // at generation time, so there's deliberately no separate RELEASE_KEY_PASSWORD.
                keyPassword = System.getenv("RELEASE_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("RELEASE_KEY_ALIAS")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            if (System.getenv("RELEASE_KEYSTORE_PATH") != null) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.14"
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

kotlin {
    sourceSets.all {
        kotlin.srcDir("src/$name/kotlin")
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.06.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.8.4")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.4")
    implementation("androidx.activity:activity-compose:1.9.1")
    // Forces a modern Fragment version across the whole dependency graph — something
    // transitive (most likely Razorpay's checkout SDK, an older library) was resolving an
    // old androidx.fragment below 1.3.0, which only ever surfaced as a release-build failure:
    // lintVitalRelease (AGP's always-on, can't-be-disabled release check) flags
    // registerForActivityResult in MainActivity.kt against any such old Fragment anywhere in
    // the graph, even though MainActivity itself has nothing to do with fragments. Debug
    // builds never run lintVital, so this was invisible until the first real release build.
    implementation("androidx.fragment:fragment-ktx:1.8.2")

    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")

    implementation("androidx.navigation:navigation-compose:2.7.7")

    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    ksp("androidx.room:room-compiler:2.6.1")

    implementation("androidx.datastore:datastore-preferences:1.1.1")

    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")

    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")

    implementation("androidx.work:work-runtime-ktx:2.9.1")

    // Live phlebotomist tracking (#42): the map itself, plus FusedLocationProviderClient for
    // reading the phlebotomist's own device location to report while en route.
    implementation("com.google.android.gms:play-services-maps:18.2.0")
    implementation("com.google.maps.android:maps-compose:4.3.3")
    implementation("com.google.android.gms:play-services-location:21.3.0")

    // Firebase: Auth (real phone OTP), Firestore (cross-role sync), Messaging (push),
    // Functions (privileged server-side logic like payment verification). BOM pins all
    // Firebase artifact versions together so they stay compatible.
    implementation(platform("com.google.firebase:firebase-bom:33.1.2"))
    implementation("com.google.firebase:firebase-auth-ktx")
    implementation("com.google.firebase:firebase-firestore-ktx")
    implementation("com.google.firebase:firebase-messaging-ktx")
    implementation("com.google.firebase:firebase-functions-ktx")

    // Razorpay's own checkout UI (card/UPI/wallet selection, OTP-based 2FA) — RBI mandates
    // this be a real payment gateway UI, not a plain API call. Order creation and payment
    // verification happen server-side (functions/src/index.ts createRazorpayOrder /
    // verifyRazorpayPayment); this SDK only launches the checkout screen and reports back
    // the payment ID/signature the client hands to that verification function.
    implementation("com.razorpay:checkout:1.6.33")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.1")

    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
}
