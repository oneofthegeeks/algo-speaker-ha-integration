# Algo Speakers for Home Assistant

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

## Development

See [CLAUDE.md](CLAUDE.md) for the layout and test commands.
