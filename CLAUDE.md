# E-Paper dashboard

ESP32 + Waveshare 2.13" V4 e-paper display for a homelab. A FastAPI server
renders "scenes" (stocks, bitcoin, weather, OctoPrint, notifications, clock)
with Pillow and pushes them to the ESP32 as 4000-byte 1-bit frames over HTTP.

- `src/`: firmware (PlatformIO, Arduino core 2.0.17, ESP32Async web server).
  WiFi credentials go in `src/config/Secrets.h`, which is gitignored. Copy it
  from `Secrets.h.example`.
- `server/`:
  - `app.py`: API and ESP32 I/O.
  - `scene_manager.py`: rotation.
  - `scenes/`: one file per scene.
  - `templates/index.html`: dashboard, vanilla JS, no build step.
  - Runtime settings with API keys live in `scene_config.json` or `data/`, both gitignored.
- `tools/epaper_client.py`: talks to the ESP32 directly, without the server.

**Setting up or deploying on a machine: follow `DEPLOY.md` step by step.**

## Checks before pushing

- **Firmware builds:** `pio run` must end with SUCCESS. It needs `Secrets.h`; for a
  build-only check, copy the example into a temporary copy of the project.
  Hardware isn't available to agents, so firmware changes are compile-checked
  only. Say so.
- **Server works:** run it with `server/run.sh` and open http://localhost:8000.
  The dashboard must load without console errors and the scenes must render
  (`/api/scenes/<id>/preview`). Without an ESP32, point `POST /api/device/config`
  at a small fake HTTP server that accepts `POST /api/display/raw`.
- **Docker:** in `server/`, run `docker compose up -d --build`. The container must
  become healthy and the logs must show the fonts loading from `/app/fonts`.

## Conventions

- Code, comments and docs are in English. The owner writes in Lithuanian.
- `server/requirements.txt` is pinned on purpose. Starlette 1.0 once broke the
  dashboard through an unpinned dependency. Bump versions deliberately and
  re-test the dashboard.
- Frame format: 122 x 250 portrait, 1 bit per pixel, MSB first, 1 = white,
  rows padded to 16 bytes. Scenes draw 250 x 122 landscape; `to_raw_bytes()`
  rotates the image.
