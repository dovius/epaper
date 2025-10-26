// #include <Arduino.h>
// #include <WiFi.h>
// #include <WebServer.h>
// #include "DEV_Config.h"
// #include "EPD.h"
// #include "GUI_Paint.h"

// const char* ssid = "GL-MT6000-887";
// const char* password = "valgykCepelina";

// WiFiServer server(80);
// UBYTE *BlackImage = NULL;
// UWORD Imagesize = 0;

// void sendResponse(WiFiClient &client, int code, String contentType, String body) {
//     client.printf("HTTP/1.1 %d OK\r\n", code);
//     client.printf("Content-Type: %s\r\n", contentType.c_str());
//     client.printf("Content-Length: %d\r\n", body.length());
//     client.println("Connection: close\r\n");
//     client.print(body);
//     client.stop();
// }

// void setup() {
//     Serial.begin(115200);
//     delay(1000);
    
//     // WiFi
//     WiFi.begin(ssid, password);
//     while (WiFi.status() != WL_CONNECTED) {
//         delay(500);
//         Serial.print(".");
//     }
//     Serial.println();
//     Serial.print("IP: ");
//     Serial.println(WiFi.localIP());
    
//     // E-Paper
//     DEV_Module_Init();
//     EPD_2in13_V4_Init();
//     EPD_2in13_V4_Clear();
    
//     Imagesize = ((EPD_2in13_V4_WIDTH % 8 == 0) ? 
//                  (EPD_2in13_V4_WIDTH / 8) : 
//                  (EPD_2in13_V4_WIDTH / 8 + 1)) * EPD_2in13_V4_HEIGHT;
    
//     BlackImage = (UBYTE *)malloc(Imagesize);
//     Paint_NewImage(BlackImage, EPD_2in13_V4_WIDTH, EPD_2in13_V4_HEIGHT, 90, WHITE);
//     Paint_Clear(WHITE);
    
//     Serial.print("Buffer size: ");
//     Serial.println(Imagesize);
    
//     server.begin();
//     Serial.println("Server started!");
// }

// void loop() {
//     WiFiClient client = server.available();
    
//     if (client) {
//         Serial.println("New client");
        
//         String request = "";
//         String contentLengthStr = "";
//         bool isPost = false;
//         String path = "";
        
//         // Read headers
//         while (client.connected()) {
//             if (client.available()) {
//                 String line = client.readStringUntil('\n');
//                 line.trim();
                
//                 if (line.length() == 0) {
//                     // Empty line = end of headers
//                     break;
//                 }
                
//                 // Parse request line
//                 if (line.startsWith("POST ")) {
//                     isPost = true;
//                     int spacePos = line.indexOf(' ', 5);
//                     path = line.substring(5, spacePos);
//                 } else if (line.startsWith("GET ")) {
//                     int spacePos = line.indexOf(' ', 4);
//                     path = line.substring(4, spacePos);
//                 }
                
//                 // Parse Content-Length
//                 if (line.startsWith("Content-Length: ")) {
//                     contentLengthStr = line.substring(16);
//                 }
//             }
//         }
        
//         Serial.print("Method: ");
//         Serial.print(isPost ? "POST" : "GET");
//         Serial.print(" Path: ");
//         Serial.println(path);
        
//         // Handle GET /info
//         if (path == "/info") {
//             String json = "{\"buffer_size\":" + String(Imagesize) + 
//                          ",\"width\":" + String(EPD_2in13_V4_WIDTH) +
//                          ",\"height\":" + String(EPD_2in13_V4_HEIGHT) + "}";
//             sendResponse(client, 200, "application/json", json);
//         }
//         // Handle POST /display
//         else if (isPost && path == "/display") {
//             size_t contentLength = contentLengthStr.toInt();
//             Serial.print("Content-Length: ");
//             Serial.println(contentLength);
            
//             if (contentLength != Imagesize) {
//                 sendResponse(client, 400, "text/plain", "Wrong size");
//             } else {
//                 // Read binary body
//                 size_t bytesRead = 0;
//                 unsigned long timeout = millis();
                
//                 while (bytesRead < contentLength && (millis() - timeout < 5000)) {
//                     if (client.available()) {
//                         BlackImage[bytesRead++] = client.read();
//                         timeout = millis();
//                     }
//                     yield();
//                 }
                
//                 Serial.print("Read: ");
//                 Serial.println(bytesRead);
                
//                 if (bytesRead == contentLength) {
//                     EPD_2in13_V4_Display_Partial(BlackImage);
//                     sendResponse(client, 200, "text/plain", "OK");
//                     Serial.println("Display updated!");
//                 } else {
//                     sendResponse(client, 500, "text/plain", "Incomplete");
//                 }
//             }
//         }
//         // Handle POST /display_full
//         else if (isPost && path == "/display_full") {
//             size_t contentLength = contentLengthStr.toInt();
            
//             if (contentLength != Imagesize) {
//                 sendResponse(client, 400, "text/plain", "Wrong size");
//             } else {
//                 size_t bytesRead = 0;
//                 unsigned long timeout = millis();
                
//                 while (bytesRead < contentLength && (millis() - timeout < 5000)) {
//                     if (client.available()) {
//                         BlackImage[bytesRead++] = client.read();
//                         timeout = millis();
//                     }
//                     yield();
//                 }
                
//                 if (bytesRead == contentLength) {
//                     EPD_2in13_V4_Init();
//                     EPD_2in13_V4_Display_Base(BlackImage);
//                     sendResponse(client, 200, "text/plain", "OK");
//                     Serial.println("Display updated (full)!");
//                 } else {
//                     sendResponse(client, 500, "text/plain", "Incomplete");
//                 }
//             }
//         }
//         else {
//             sendResponse(client, 404, "text/plain", "Not found");
//         }
        
//         client.stop();
//     }
// }