# Changelog

| Version | Date | Changes |
|---|---|---|
| 2.0.3 | 2026-11-22 | A device that refuses one correctly signed request (seen on an 8301, about once in several hundred polls) no longer shows "authentication expired" and stops being polled: a refused Standard-auth request is signed again once, and re-authentication is only asked for after three refused polls in a row. |
| 2.0.2 | 2026-11-22 | Ready for other users: default stations are SomaFM only (the old list had region-locked commercial streams); README gains a tested-devices table, troubleshooting and badges; bug and feature issue forms; SECURITY.md; tests and examples use documentation addresses (192.0.2.x). Existing entries keep their own station list. |
| 2.0.1 | 2026-11-21 | Radio status and Now playing refresh again 6 s after a play or stop, once the 8301 has updated its own status (it lags a few seconds). |
| 2.0.0 | 2026-11-20 | Rewrite as a Home Assistant custom integration (`algo_speaker`), replacing the python_scripts attempt. Config flow with shared password, explicit auth mode (Standard/Basic/None; Basic https-only) and hosts; options for hosts, stations and poll interval; reauth and reconfigure. Per-device volumes, tone buttons, status sensors; 8301 Music switch, Station select and Now playing; Strobe switch on strobe models; read-only support for old firmware. Services: play/stop tone, strobe start/stop, play/stop stream. Diagnostics. |
| 1.0.0 | 2025-09-17 | python_scripts version (HMAC generator script, REST commands, example dashboard). Never worked: HA python_scripts cannot sign requests (issue #1). |
