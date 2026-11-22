"""Constants for the Algo Speakers integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "algo_speaker"
MANUFACTURER: Final = "Algo"

CONF_HOSTS: Final = "hosts"
CONF_STATIONS: Final = "stations"
CONF_SCAN_INTERVAL: Final = "scan_interval"
# "standard" (HMAC, default), "basic" (https only) or "none". Chosen explicitly, never guessed.
CONF_AUTH_MODE: Final = "auth_mode"
# Per-host identity (model, MAC, firmware, read-only) cached in entry.data so a device that is
# offline when Home Assistant starts still gets its entities (shown unavailable) instead of
# holding back the whole entry.
CONF_DEVICES: Final = "devices"

DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 10
MAX_SCAN_INTERVAL: Final = 3600

# Algo volume scale: 0 dB (loudest) down to -45 dB, in 3 dB steps only. The device stores any
# string it is sent, so everything written is snapped onto this grid first.
VOLUME_MIN_DB: Final = -45
VOLUME_MAX_DB: Final = 0
VOLUME_STEP_DB: Final = 3

KEY_PAGE_VOL: Final = "audio.page.vol"
KEY_RING_VOL: Final = "audio.ring.vol"
KEY_MCAST_MODE: Final = "mcast.mode"
KEY_RADIO_USE: Final = "radio.use"
KEY_RADIO_URL: Final = "radio.url"
KEY_RADIO_FN: Final = "radio.fn"
KEY_RADIO_ZONE: Final = "radio.zone"

MCAST_MODES: Final = {"0": "Off", "1": "Sender", "2": "Receiver"}

# Multicast zone 7 is "Music" on every Algo: the lowest priority, so a page pauses it.
MUSIC_ZONE: Final = "7"
RADIO_MODEL: Final = "8301"
STATUS_RADIO: Final = "Internet Radio Streaming"
RADIO_STREAMING: Final = "Multicasting URL audio"

# Only these models have a strobe; the rest answer 200 to strobe/start and do nothing.
STROBE_MODELS: Final = frozenset({"8128", "8138", "8190S", "8410", "8420"})
STROBE_COLORS: Final = ("red", "blue", "green", "amber")
# ledlvl per brightness name; the 8190S uses 1/2/3 instead of 0/56/255.
STROBE_BRIGHTNESS: Final = {"low": 0, "medium": 56, "high": 255}
STROBE_BRIGHTNESS_8190S: Final = {"low": 1, "medium": 2, "high": 3}
STROBE_DEFAULT_PATTERN: Final = 2
STROBE_DEFAULT_COLOR: Final = "red"

# Starter list for a new entry (edit it in the entry's options). SomaFM: listener-supported,
# no ads, stable URLs that work in any region.
DEFAULT_STATIONS: Final = """Groove Salad | https://ice5.somafm.com/groovesalad-128-aac
Beat Blender | https://ice5.somafm.com/beatblender-128-aac
Fluid | https://ice5.somafm.com/fluid-128-aac
Drone Zone | https://ice2.somafm.com/dronezone-128-aac
Secret Agent | https://ice5.somafm.com/secretagent-128-aac
Lush | https://ice5.somafm.com/lush-128-aac
Doomed | https://ice5.somafm.com/doomed-128-aac"""

SERVICE_PLAY_TONE: Final = "play_tone"
SERVICE_STOP_TONE: Final = "stop_tone"
SERVICE_STROBE_START: Final = "strobe_start"
SERVICE_STROBE_STOP: Final = "strobe_stop"
SERVICE_PLAY_STREAM: Final = "play_stream"
SERVICE_STOP_STREAM: Final = "stop_stream"
