# Algo Speakers for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories/)
[![Validate](https://github.com/oneofthegeeks/algo-speaker-ha-integration/actions/workflows/validate.yml/badge.svg)](https://github.com/oneofthegeeks/algo-speaker-ha-integration/actions/workflows/validate.yml)
[![CI](https://github.com/oneofthegeeks/algo-speaker-ha-integration/actions/workflows/ci.yml/badge.svg)](https://github.com/oneofthegeeks/algo-speaker-ha-integration/actions/workflows/ci.yml)

Not affiliated with or endorsed by Algo Communication Products.

A custom integration for [Algo](https://www.algosolutions.com/) IP speakers, paging adapters,
displays and strobes, over their REST API. Set the volumes, play tones, flash the strobe, and
run the 8301's internet radio (multicast to every speaker's music zone) from Home Assistant.
Local polling, no cloud.

## Install (HACS)

1. HACS > three-dot menu > **Custom repositories** > add
   `https://github.com/oneofthegeeks/algo-speaker-ha-integration`, category **Integration**.
2. Install **Algo Speakers**, then restart Home Assistant.
3. **Settings > Devices & services > Add integration > Algo Speakers.**

## Setup

On each device, enable the REST API (Advanced Settings > Admin) and note its authentication
mode. One integration entry covers every device that shares a password and mode:

| Field | What to enter |
|---|---|
| REST API password | The device's RESTful API password. Blank when its authentication is None. |
| Authentication | **Standard** (HMAC signed, default), **Basic** (https only) or **None**: must match the device. |
| Device addresses | IPs or hostnames, separated by commas or new lines. |

Each address is checked before the entry is created. Devices need a correct clock (NTP):
Standard auth rejects requests more than about 30 seconds off.

**Options** (the entry's Configure button): add or remove addresses, change the
authentication mode, edit the radio stations (one `Name | URL` per line) and the poll
interval (default 30 s). **Reconfigure** changes the password and addresses; a refused
password starts a re-authentication prompt.

## Tested with

| Device | Firmware | Notes |
|---|---|---|
| 8301 Paging Adapter | 5.7 | Internet radio sender (Music switch, Station select). |
| 8410 Display Speaker | 5.7 | Volumes, tones, strobe. |
| 8188 Ceiling Speaker | 5.7.2 | Volumes, tones. |
| Any model | 3.x | Read-only (see Known limits). |

Home Assistant 2025.8 or newer. Other Algo models on firmware 5.x use the same API and should
work; if you try one, an issue saying how it went is welcome.

## Entities

| Entity | Models | What it does |
|---|---|---|
| Number "Music/page volume" | all (fw 5.x) | `audio.page.vol`: music, multicast and pages. 0 to -45 dB in 3 dB steps. |
| Number "Ring volume" | all (fw 5.x) | `audio.ring.vol`: local tones and alerts. |
| Button "Test tone" / "Stop tone" | all (fw 5.x) | Built-in test tone; stop any tone. |
| Sensor "SIP registration" | all (fw 5.4+) | From the device status. |
| Sensor "Multicast mode" | all | Sender/receiver and stream counts. |
| Sensor "Firmware" (diagnostic) | all (fw 5.x) | Firmware version. |
| Switch "Music" | 8301 | On plays the selected station; off stops. |
| Select "Station" | 8301 | Choosing a station plays it at once. |
| Sensor "Now playing" | 8301 | Station name, the raw URL if it isn't in your list, or "Stopped". |
| Sensor "Radio status" | 8301 | The device's own "Internet Radio Streaming" status. |
| Switch "Strobe" | 8128, 8138, 8190S, 8410, 8420 | Pattern 2, red, full brightness. |
| Sensors "Music/page volume", "Ring volume" | old firmware (3.x) | Read-only, see Known limits. |

An example dashboard (Mushroom cards) is in [`examples/dashboard.yaml`](examples/dashboard.yaml).

## Services

Each takes `device_id` (one or more Algo devices).

| Service | Fields |
|---|---|
| `algo_speaker.play_tone` | `file` (e.g. `chime.wav`), `loop`, optional `volume_db` (sets the ring volume first) |
| `algo_speaker.stop_tone` | |
| `algo_speaker.strobe_start` | `pattern` 0-15, `color1`, `color2`, `brightness` low/medium/high |
| `algo_speaker.strobe_stop` | |
| `algo_speaker.play_stream` | `url` (8301 only) |
| `algo_speaker.stop_stream` | (8301 only) |

```yaml
action: algo_speaker.play_tone
data:
  device_id: 0123456789abcdef0123456789abcdef
  file: chime.wav
  volume_db: -12
```

## How the music works

The 8301 pulls an internet stream and multicasts it on zone 7 ("Music", the lowest priority,
so a page pauses it and it resumes). Speakers that listen on zone 7 play it at their page volume.
This integration follows the same convention as an Algo 8450 console's buttons, so both can
drive the same 8301:

- **Play:** `radio.use = "1"`, `radio.url = <stream>`, `radio.fn = ""` (an offline file would
  win when the stream fails), `radio.zone = "7"`.
- **Stop:** `radio.url = ""`. `radio.use` stays `"1"`.
- Music is on when `radio.use` is `"1"` and `radio.url` is set.

Because Stop clears the URL, the Music switch remembers the last station it saw playing and
plays that when turned back on (the first station in your list after a restart).

## Known limits

- **Old firmware (3.x) is read-only.** It has no `/api/info/about` and refuses settings
  writes. Its volumes and multicast mode show as sensors, and a repair issue says why.
- **Strobe state is assumed.** The device can't report it, so the switch shows the last command
  Home Assistant sent.
- **TLS certificates are not verified.** Each device has its own self-signed certificate
  and there is no CA to check it against. https still keeps the traffic private on the LAN,
  but it does not prove the device is the one you meant.
- **Basic authentication is only sent over https.** It carries the password in recoverable
  form. A device that answers only on http needs Standard auth (HMAC, which never reveals the
  password) or None. Standard and None fall back to http when https can't connect, with a
  warning in the log.
- Devices answer one request at a time (~300 ms each), so a poll takes a second or two per
  device. Keep the poll interval at 10 s or more.

## Troubleshooting

- **"Cannot connect" when adding a device:** check the REST API is enabled on it (Advanced
  Settings > Admin) and that Home Assistant can reach its address.
- **"Invalid authentication" with the right password:** the authentication mode must match the
  device's own setting, and Standard needs the device's clock within about 30 s of real time
  (set an NTP server on the device).
- **"Authentication expired" now and then, on one device:** fixed in 2.0.3. Some devices
  refuse an occasional good request; the integration now signs it again and only asks for
  the password after three refused polls in a row.
- **Music switch is on but nothing plays:** the speakers must listen on multicast zone 7 (each
  receiver's Multicast settings), and the stream URL must play in a normal media player.
- **Reporting a problem:** open an issue with your Home Assistant version, the Algo model and
  firmware, and the integration's diagnostics (device page > Download diagnostics; the password
  and SIP details are redacted).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security problems: [SECURITY.md](SECURITY.md).
