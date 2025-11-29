# Ultimate E-Paper Dashboard

This project transforms your ESP32 + 2.13" E-Paper display into a smart dashboard that displays:
- **Real-time Clock** (NTP synced)
- **Local Weather** (Temperature & Condition via Open-Meteo)
- **Hacker News Top Stories**
- **WiFi Signal Status**

## Features
- **Deep Sleep**: The device sleeps between updates (every 10 minutes) to save battery.
- **Robust Parsing**: Uses `ArduinoJson` for reliable API handling.
- **Custom Graphics**: Includes custom icons for Weather and WiFi.
- **Fast Refresh**: Optimized display updates.

## Configuration
Open `src/main.cpp` and update the following:

1. **WiFi Credentials**:
   ```cpp
   const char* WIFI_SSID = "YOUR_WIFI_SSID";
   const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
   ```

2. **Location (for Weather)**:
   Get your Latitude/Longitude from Google Maps or similar.
   ```cpp
   const float LATITUDE = 37.7749;
   const float LONGITUDE = -122.4194;
   ```

3. **Timezone**:
   Adjust `UTC_OFFSET_SEC` (e.g., -28800 for PST).

## Dependencies
This project uses PlatformIO. Dependencies are automatically installed:
- `ArduinoJson`
- `NTPClient`

## Hardware
- ESP32 Board (e.g., ESP-WROVER-KIT or generic ESP32)
- Waveshare 2.13" E-Paper Display V4


