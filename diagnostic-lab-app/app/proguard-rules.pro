-keep class com.digitalsolutions.diagnosticlab.data.local.entities.** { *; }

# Razorpay Checkout SDK — required by Razorpay's own integration docs so its webview bridge
# and callback classes survive minification.
-keep class com.razorpay.** { *; }
-keepclasseswithmembers class * {
  @android.webkit.JavascriptInterface <methods>;
}
-keepattributes JavascriptInterface
-dontwarn com.razorpay.**
-optimizations !method/inlining/*
