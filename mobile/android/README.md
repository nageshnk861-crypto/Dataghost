# DataGhost Android Enterprise Agent

A production-oriented Android Enterprise DLP agent for the DataGhost platform.

## Enrollment Architecture

```
ADMIN (DataGhost Dashboard)
  └─ Devices → Add Device → Android
       └─ Choose enrollment mode:
            ├─ Work Profile (BYOD)       → User installs DataGhost Agent app
            │                              → Opens app → Scans QR code
            │                              → Work Profile created automatically
            │
            └─ Fully Managed (Corporate) → Factory reset device
                                         → Setup wizard: tap screen 6× quickly
                                         → "Set up with QR code"
                                         → Scan QR → DataGhost Agent downloads
                                           & installs automatically via DPC
                                         → Device silently enrolled, appears
                                           in dashboard within ~10 seconds
```

No separate "QR scanner app" is needed. The enrollment QR is an **Android Enterprise DPC-compatible** payload.

---

## Project Structure

```
mobile/android/
├─ app/
│  ├─ build.gradle
│  └─ src/main/
│     ├─ AndroidManifest.xml
│     ├─ res/
│     │  ├─ values/strings.xml
│     │  └─ xml/
│     │     ├─ device_admin_policies.xml   ← Device admin capabilities
│     │     └─ network_security_config.xml ← HTTPS enforcement
│     └─ java/com/dataghost/agent/
│        ├─ DataGhostApp.kt                ← Application entry point
│        ├─ enrollment/
│        │  ├─ DataGhostDeviceAdminReceiver.kt  ← Android Enterprise DPC ★
│        │  └─ EnrollmentManager.kt             ← API registration logic
│        ├─ heartbeat/
│        │  ├─ HeartbeatWorker.kt          ← WorkManager periodic heartbeat
│        │  └─ BootReceiver.kt             ← Restart heartbeat on reboot
│        ├─ dlp/
│        │  └─ DlpScannerService.kt        ← Work Profile DLP monitoring
│        ├─ models/
│        │  └─ DeviceModels.kt             ← API data contracts
│        └─ ui/
│           ├─ MainActivity.kt             ← Post-enrollment dashboard
│           └─ EnrollmentActivity.kt       ← Manual QR / code entry
├─ build.gradle
└─ settings.gradle
```

---

## Key Component: DataGhostDeviceAdminReceiver

The `DataGhostDeviceAdminReceiver` is the Android Enterprise **Device Policy Controller (DPC)**. It:

1. Receives `onProfileProvisioningComplete()` from the Android setup wizard after QR scan
2. Extracts the DataGhost server URL and enrollment token from `PROVISIONING_ADMIN_EXTRAS_BUNDLE`
3. Calls `POST /api/devices/enrollment/register` silently in the background
4. Stores credentials in SharedPreferences
5. Launches `MainActivity` with a success confirmation
6. Schedules the WorkManager heartbeat

---

## QR Code Payload Format

The DataGhost backend generates a dual-format QR payload (via `/api/devices/enrollment/create-android-enterprise`):

```json
{
  "version": "1.0",
  "server_url": "https://xxxx-3000.inc1.devtunnels.ms",
  "token": "<raw_enrollment_token>",
  "code": "DG-XXXX-XXXX",
  "platform": "Android",
  "expires_at": "2024-01-01T00:10:00",

  "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME":
    "com.dataghost.agent/com.dataghost.agent.enrollment.DataGhostDeviceAdminReceiver",

  "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION":
    "https://xxxx-3000.inc1.devtunnels.ms/dataghost-agent.apk",

  "android.app.extra.PROVISIONING_SKIP_ENCRYPTION": false,

  "android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE": {
    "com.dataghost.SERVER_URL": "https://xxxx-3000.inc1.devtunnels.ms",
    "com.dataghost.ENROLLMENT_TOKEN": "<raw_token>",
    "com.dataghost.ENROLLMENT_CODE": "DG-XXXX-XXXX",
    "com.dataghost.EXPIRES_AT": "2024-01-01T00:10:00"
  }
}
```

---

## Building the APK

**Prerequisites:** Android Studio or Android SDK with Gradle

```bash
cd mobile/android
./gradlew assembleDebug          # Debug APK
./gradlew assembleRelease        # Release APK (needs signing config)
```

Output: `app/build/outputs/apk/debug/app-debug.apk`

---

## Dev Tunnel Notes

- **Single tunnel (port 3000 only):** Set `SERVER_PUBLIC_URL` to the frontend tunnel URL.
  Android API calls route through Next.js `/api/*` proxy → local backend.

- **Dual tunnels (3000 + 8000):** Set `SERVER_PUBLIC_URL` to the **backend** tunnel URL.
  Android calls the backend directly.

Update `backend/.env` accordingly before generating enrollment QR codes.

---

## Adding Camera QR Scanning

Uncomment the ML Kit dependencies in `app/build.gradle`:

```gradle
implementation 'com.google.mlkit:barcode-scanning:17.2.0'
implementation 'androidx.camera:camera-camera2:1.3.1'
implementation 'androidx.camera:camera-lifecycle:1.3.1'
implementation 'androidx.camera:camera-view:1.3.1'
```

Then implement the camera preview in `EnrollmentActivity.startQrScanner()` and call
`onQrCodeScanned(rawValue)` when a barcode is detected.
