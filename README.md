# Schulnetz to Home Assistant

Home Assistant integration for the Swiss **Schulnetz** (schulnetz.lu.ch) student
portal. It scrapes your current marks and upcoming tests via a Playwright-based
Node server and exposes them in Home Assistant — one **device per subject**, one
**sensor per test/exam**, plus an average sensor, with a fully configurable
naming scheme.

New marks and tests are detected automatically: a newly published grade updates
the existing sensor, a newly listed test creates a new sensor, and a removed
test removes its sensor.

## Architecture

```
Schulnetz  ──Playwright──►  Node server (Docker)  ──plain HTTP──►  Home Assistant
                            · scrapes marks/tests                   · device per subject
                            · stores credentials                    · sensor per exam
                            · GET/POST /api/*                       · naming scheme
```

---

## 1. Install the Home Assistant integration (HACS)

Add this repository to HACS as a custom integration, then install **Schulnetz**.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=The12Forest&repository=Schulnetz-to-HomeAssistant-Integration&category=integration)

> The custom integration lives in `custom_components/schulnetz`. The Node
> server is **not** installed by HACS — run it as a Docker container (below).

## 2. Run the Node server (Docker)

The container bundles the Chromium browser, the Playwright scraper and the HTTP
server. It listens on internal port **80** by default (change via `PORT`).

### Option A — pull from GitHub Container Registry

```yaml
# docker-compose.prod.yml
services:
  schulnetz:
    image: ghcr.io/the12forest/schulnetz-to-ha-integration:latest
    pull_policy: always
    restart: unless-stopped
    environment:
      PORT: "80"
      # SCHULNETZ_EMAIL: "you@example.com"
      # SCHULNETZ_PASSWORD: "your-password"
      # SCHULNETZ_TOTP_SECRET: "your-totp-secret"
    ports:
      - "80:80"
    volumes:
      - schulnetz-data:/app/data
volumes:
  schulnetz-data:
```

```bash
docker compose -f docker-compose.prod.yml up -d
```

### Option B — build from source (development)

```bash
docker compose -f docker-compose.dev.yml up -d
```

### Option C — plain `docker run`

```bash
docker run -d \
  --name schulnetz \
  -p 80:80 \
  -v schulnetz-data:/app/data \
  ghcr.io/the12forest/schulnetz-to-ha-integration:latest
```

### Environment variables

| Variable                | Default  | Description                                                              |
| ----------------------- | -------- | ------------------------------------------------------------------------ |
| `PORT`                  | `80`     | Internal HTTP port the server listens on.                                |
| `SCHULNETZ_URL`         | `https://schulnetz.lu.ch/bbzw` | Schulnetz portal URL (full URL, overrides the school code). |
| `SCHULNETZ_SCHOOL`      | `bbzw`   | Schulnetz school code (path under schulnetz.lu.ch, e.g. `ksalp`, `fmz`). |
| `DATA_DIR`              | `/app/data` | Directory for persisted config + cached state.                         |
| `MIN_SCRAPE_INTERVAL_MS`| `600000` | Minimum time between two scrapes (throttle, protects your account).      |
| `SCHULNETZ_EMAIL`       | —        | Schulnetz email. **Overrides** credentials saved via Home Assistant.     |
| `SCHULNETZ_PASSWORD`    | —        | Schulnetz password.                                                      |
| `SCHULNETZ_TOTP_SECRET` | —        | TOTP secret (the token used to generate the one-time code).              |

### Credentials and school precedence

- **Docker environment** (`SCHULNETZ_EMAIL/PASSWORD/TOTP_SECRET` and
  `SCHULNETZ_URL`/`SCHULNETZ_SCHOOL`) **wins** — if set, those values are used
  and ignore anything else.
- Otherwise, the credentials and school chosen in the **Home Assistant config
  flow** are pushed to the server and **persisted** to disk
  (`/app/data/config.json`), so they survive container restarts.

## 3. Configure the integration in Home Assistant

1. In Home Assistant go to **Settings → Devices & Services → Add Integration**.
2. Select **Schulnetz**.
3. Enter the server **Host** and **Port** (default `80`, matching the Docker
   `80:80` mapping — change if you published a different host port).
4. Choose your **School** from the list (defaults to *Berufsbildungszentrum
   Wirtschaft, Informatik und Technik* — `bbzw`). Pick **Custom…** to paste a
   different school link instead.
5. Enter your **Email**, **Password** and **TOTP secret**. These are sent to the
   Node server, which uses them to log in and scrape your data.
6. Done — a device per subject appears with its sensors.

> The school is fixed at install time. To switch schools later, delete and
> re-add the integration.

### Sensors

Each subject is a **device**. Under it you get:

- an **average** sensor (`… Durchschnitt`) with the subject's current average,
- per test/exam:
  - the **grade** (`note`),
  - the **date** (a real date entity),
  - the **weight** (`Gewichtung`),
  - the achieved **points** (`Punkte`),
  - the **class average** (`Klassenschnitt`),
  - the **max points** (`Max. Punkte`), only if the portal shows them.

All numeric values are real numbers. Pending (not yet graded) exams show
"unknown" and carry a `pending` boolean attribute you can use in automations.

### Naming scheme

In the integration **Options** you can configure:

- **Refresh interval** (minutes) — how often Home Assistant triggers a scrape.

- **Subject naming template** — how a subject is named. Default `{full}` (the
  raw name). Available placeholders:

  | Placeholder | Meaning                                        |
  | ----------- | ---------------------------------------------- |
  | `{full}`    | The raw subject string, e.g. `BMDE-E-BMLT25b-MovDeutsch` |
  | `{first}`   | First dash-separated segment (`BMDE`)          |
  | `{last}`    | Last dash-separated segment (`MovDeutsch`)     |
  | `{seg1}`…`{segN}` | Individual dash-separated segments      |
  | `{alias}`   | The alias you set below, if any               |

  Example: `{seg1} {last}` → `BMDE MovDeutsch`.

- **Exam naming template** — how a test/exam is named. Default `{exam}` (the
  test's name). Placeholders: `{subject}` (the subject's display name),
  `{exam}` (test name), `{date}`, plus all subject placeholders.

- **Subject aliases** — one per line in the form `raw = alias`, to override the
  template for specific subjects. Example:

  ```
  BMDE-E-BMLT25b-MovDeutsch = Deutsch
  M320-S-INA25aL-Bur320 objektorientiert programmieren = Programmieren
  ```

## HTTP API

| Method | Path           | Description                                          |
| ------ | -------------- | ---------------------------------------------------- |
| POST   | `/api/config`  | Set email/password/TOTP secret and school (persisted). |
| GET    | `/api/config`  | Whether credentials are configured, plus school (no secrets). |
| POST   | `/api/scrape`  | Run a scrape now (blocking, throttled).              |
| GET    | `/api/state`   | Last scraped subjects/exams (cached).                |
| GET    | `/api/status`  | Scrape status, last run, next allowed time.          |
| GET    | `/api/health`  | Liveness check.                                      |

> **Note:** communication between Home Assistant and the Node server is plain
> HTTP by design — run it on a trusted LAN only.
