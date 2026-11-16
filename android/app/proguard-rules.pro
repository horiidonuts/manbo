# ML Kit (the QR scanner for pairing with a PC) wires its parts together through
# Firebase-style component registrars found by reflection; R8's full mode breaks
# that (GmsBarcodeScanning.getClient crashes with a null SharedPrefManager).
-keep class com.google.mlkit.** { *; }
-keep class com.google.firebase.components.** { *; }
-keep class com.google.android.gms.internal.mlkit_code_scanner.** { *; }
