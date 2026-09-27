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
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
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
