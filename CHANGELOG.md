# Changelog

| Version | Date | Changes |
|---|---|---|
| 2.0.0 | 2026-11-20 | Rewrite as a Home Assistant custom integration (`algo_speaker`), replacing the python_scripts attempt. Config flow with shared password, explicit auth mode (Standard/Basic/None; Basic https-only) and hosts; options for hosts, stations and poll interval; reauth and reconfigure. Per-device volumes, tone buttons, status sensors; 8301 Music switch, Station select and Now playing; Strobe switch on strobe models; read-only support for old firmware. Services: play/stop tone, strobe start/stop, play/stop stream. Diagnostics. |
| 1.0.0 | 2025-09-17 | python_scripts version (HMAC generator script, REST commands, example dashboard). Never worked: HA python_scripts cannot sign requests (issue #1). |
