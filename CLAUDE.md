# algo-speaker-ha-integration

Live: v2.0.1 (2026-11-21) — installed on Taylor's Home Assistant for the house Algo devices.

## What This Is
Home Assistant custom integration (domain `algo_speaker`, HACS) for Taylor's Algo IP speakers,
paging adapters and strobes: volumes, tones, strobe, and the 8301's internet radio. Public repo.

## Stack
- Python 3.13, Home Assistant custom integration, `aiohttp` via HA's shared session. No
  external requirements.
- Algo REST API with Standard (HMAC-SHA256), Basic or None auth.
- Tests: pytest + `pytest-homeassistant-custom-component`. Lint: ruff.

## Local Development
```bash
git clone git@github.com:oneofthegeeks/algo-speaker-ha-integration.git
cd algo-speaker-ha-integration
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements_test.txt
```
To try it in a real HA: copy `custom_components/algo_speaker/` into HA's
`config/custom_components/` and restart.

## Testing
```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pytest -q
```
- `tests/test_api.py`: signing (Algo's published vectors), https/http fallback, auth modes,
  read-only detection, radio.url unescape.
- `tests/test_config_flow.py`: user/reauth/reconfigure/options flows, station parsing.
- `tests/test_entities.py`: full entry setup against `tests/devices.py` (simulated 8301, 8410
  and firmware 3.x devices that check the HMAC like the real ones).
- hassfest locally: `docker run --rm -v "$PWD":/github/workspace ghcr.io/home-assistant/hassfest`.
- The commit gate hook only runs npm scripts, so it does nothing here: run the line above
  before committing.

## Deployment
Bump `version` in `manifest.json` and `pyproject.toml`, add a CHANGELOG row, then
`git tag vX.Y.Z && git push --tags` and create a GitHub release from the tag; HACS offers the
release as an update. CI: `ci.yml` (ruff + pytest), `validate.yml` (hassfest + HACS).

## Key Files
- `custom_components/algo_speaker/api.py`: REST client: signing, scheme fallback, auth modes,
  typed errors, radio/volume helpers. No HA imports.
- `coordinator.py`: one coordinator per device; capability flags (`is_radio`, `has_strobe`,
  `read_only`) and device info.
- `__init__.py`: setup (identify each host, cached identity for offline ones), repair issue,
  stale device cleanup. `services.py`: the six services.
- `config_flow.py`: user/reauth/reconfigure + options (hosts, auth mode, stations, interval).
- `number.py`, `switch.py`, `select.py`, `sensor.py`, `button.py`: entities.
- `strings.json` = `translations/en.json` (keep them identical).
- `examples/dashboard.yaml`: example Mushroom view.

## Gotchas
- **Tests pin HA 2026.2.3** (`pytest-homeassistant-custom-component==0.13.316`): the last
  release on Python 3.13. Taylor's HA (2026.11) runs Python 3.14, so API changes after
  February are only caught by hassfest (which runs current HA) and real use. Moving CI to
  Python 3.14 would unlock the current test package.
- **Auth mode is explicit** (security review, 2026-11-20): no Standard to Basic fallback.
  Basic is never sent over http; Standard/None fall back to http, warned once per device.
- **TLS verification is off** (`ssl=False`): per-device self-signed certs, no CA.
- **Devices are single-threaded** (~300 ms a request): each `AlgoClient` holds a lock; never
  fire parallel requests at one device.
- **The device stores whatever it is sent**: volumes are snapped to 0..-45 in 3 dB steps and
  read back; play_stream reads radio.url back.
- **8301 returns radio.url HTML-escaped**: unescaped in `get_setting`.
- **Music convention** (shared with the 8450 console): PLAY sets use/url/fn/zone; STOP only
  clears radio.url. The Music switch remembers the last station in memory only.
- **Firmware 3.x**: about/status 404 and PUT 400/404, so read-only. Identified by host, not MAC.
- Device identity is cached in `entry.data["devices"]`: an offline device that was seen
  before loads unavailable; one never seen makes the entry retry setup.
- Hosts and auth mode live in `entry.data` but are copied into options so a change to them
  alone still triggers `OptionsFlowWithReload`'s reload.
- Strobe state is assumed (no read-back).
