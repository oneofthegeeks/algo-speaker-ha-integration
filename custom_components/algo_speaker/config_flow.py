"""Config flow for Algo Speakers: one shared REST API password and auth mode, plus hosts."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol

from .api import AUTH_BASIC, AUTH_MODES, AUTH_STANDARD, AlgoAuthError, AlgoClient, AlgoError
from .const import (
    CONF_AUTH_MODE,
    CONF_DEVICES,
    CONF_HOSTS,
    CONF_SCAN_INTERVAL,
    CONF_STATIONS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STATIONS,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .util import StationLineError, parse_hosts, parse_stations

_LOGGER = logging.getLogger(__name__)

TITLE = "Algo speakers"

PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
MULTILINE_SELECTOR = TextSelector(TextSelectorConfig(multiline=True))
AUTH_MODE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=list(AUTH_MODES), mode=SelectSelectorMode.LIST, translation_key="auth_mode"
    )
)


async def async_validate_hosts(
    hass: HomeAssistant, password: str, auth_mode: str, hosts: list[str]
) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, str]]:
    """Identify every host. Returns (device cache, errors, description placeholders).

    Each host is tried even after one fails, so the form can list every failing one.
    """
    session = async_get_clientsession(hass)
    devices: dict[str, dict[str, Any]] = {}
    unreachable: list[str] = []
    refused: list[str] = []
    for host in hosts:
        try:
            identity = await AlgoClient(session, host, password, auth_mode).identify()
        except AlgoAuthError:
            refused.append(host)
        except AlgoError as err:
            _LOGGER.debug("Cannot reach %s: %s", host, err)
            unreachable.append(host)
        else:
            devices[host] = identity.as_dict()
    errors: dict[str, str] = {}
    placeholders = {"hosts": ", ".join(unreachable)}
    if refused:
        errors["base"] = "invalid_auth"
        placeholders["hosts"] = ", ".join(refused)
    elif unreachable:
        # Basic is https-only, so a device reachable only on http fails here; say so.
        errors["base"] = "cannot_connect_basic" if auth_mode == AUTH_BASIC else "cannot_connect"
    return devices, errors, placeholders


def _check_credentials(password: str, auth_mode: str) -> dict[str, str]:
    """Basic auth with no password can never work."""
    if auth_mode == AUTH_BASIC and not password:
        return {CONF_PASSWORD: "password_required"}
    return {}


def _user_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_PASSWORD): PASSWORD_SELECTOR,
            vol.Required(CONF_AUTH_MODE, default=AUTH_STANDARD): AUTH_MODE_SELECTOR,
            vol.Required(CONF_HOSTS): MULTILINE_SELECTOR,
        }
    )


class AlgoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a group of Algo devices that share one REST API password."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AlgoOptionsFlow:
        """Hosts, auth mode, stations and scan interval."""
        return AlgoOptionsFlow()

    async def _async_hosts_step(
        self, step_id: str, user_input: dict[str, Any] | None, entry: ConfigEntry | None
    ) -> ConfigFlowResult:
        """Shared by user and reconfigure: password, auth mode and hosts."""
        errors: dict[str, str] = {}
        placeholders = {"hosts": ""}
        if user_input is not None:
            password = user_input.get(CONF_PASSWORD, "")
            auth_mode = user_input.get(CONF_AUTH_MODE, AUTH_STANDARD)
            hosts = parse_hosts(user_input[CONF_HOSTS])
            errors = _check_credentials(password, auth_mode)
            if not hosts:
                errors[CONF_HOSTS] = "no_hosts"
            if not errors:
                if entry is None:
                    self._async_abort_entries_match({CONF_HOSTS: hosts})
                devices, errors, placeholders = await async_validate_hosts(
                    self.hass, password, auth_mode, hosts
                )
            if not errors:
                data = {
                    CONF_PASSWORD: password,
                    CONF_AUTH_MODE: auth_mode,
                    CONF_HOSTS: hosts,
                    CONF_DEVICES: devices,
                }
                if entry is None:
                    return self.async_create_entry(title=TITLE, data=data)
                return self.async_update_reload_and_abort(entry, data_updates=data)
        suggested = user_input
        if suggested is None and entry is not None:
            suggested = {
                CONF_PASSWORD: entry.data.get(CONF_PASSWORD, ""),
                CONF_AUTH_MODE: entry.data.get(CONF_AUTH_MODE, AUTH_STANDARD),
                CONF_HOSTS: "\n".join(entry.data[CONF_HOSTS]),
            }
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(_user_schema(), suggested),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the password, auth mode and hosts."""
        return await self._async_hosts_step("user", user_input, None)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the password, auth mode and/or hosts."""
        return await self._async_hosts_step(
            "reconfigure", user_input, self._get_reconfigure_entry()
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The devices refused the stored password."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the new password and check it against every host."""
        entry = self._get_reauth_entry()
        auth_mode = entry.data.get(CONF_AUTH_MODE, AUTH_STANDARD)
        errors: dict[str, str] = {}
        placeholders = {"hosts": ""}
        if user_input is not None:
            password = user_input.get(CONF_PASSWORD, "")
            errors = _check_credentials(password, auth_mode)
            if not errors:
                devices, errors, placeholders = await async_validate_hosts(
                    self.hass, password, auth_mode, entry.data[CONF_HOSTS]
                )
                # A device that happens to be unplugged must not block a password change:
                # accept once at least one host took the password and none refused it.
                if errors.get("base") == "cannot_connect" and devices:
                    errors = {}
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_PASSWORD: password,
                        CONF_DEVICES: {**entry.data.get(CONF_DEVICES, {}), **devices},
                    },
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_PASSWORD, default=""): PASSWORD_SELECTOR}),
            errors=errors,
            description_placeholders=placeholders,
        )


class AlgoOptionsFlow(OptionsFlowWithReload):
    """Hosts, auth mode, radio stations and the poll interval. Saving reloads the entry."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """One form for everything."""
        entry = self.config_entry
        errors: dict[str, str] = {}
        placeholders = {"hosts": "", "line": ""}
        if user_input is not None:
            hosts = parse_hosts(user_input[CONF_HOSTS])
            password = entry.data.get(CONF_PASSWORD, "")
            auth_mode = user_input.get(CONF_AUTH_MODE, AUTH_STANDARD)
            errors = _check_credentials(password, auth_mode)
            try:
                parse_stations(user_input.get(CONF_STATIONS, ""))
            except StationLineError as err:
                errors[CONF_STATIONS] = "invalid_station"
                placeholders["line"] = err.line
            if not hosts:
                errors[CONF_HOSTS] = "no_hosts"
            if not errors:
                cached: dict[str, Any] = entry.data.get(CONF_DEVICES, {})
                # A changed auth mode is checked against every host; otherwise only new hosts
                # need checking and known ones keep their cached identity.
                mode_changed = auth_mode != entry.data.get(CONF_AUTH_MODE, AUTH_STANDARD)
                to_check = hosts if mode_changed else [h for h in hosts if h not in cached]
                devices, errors, found = await async_validate_hosts(
                    self.hass, password, auth_mode, to_check
                )
                placeholders["hosts"] = found["hosts"]
            if not errors:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_AUTH_MODE: auth_mode,
                        CONF_HOSTS: hosts,
                        CONF_DEVICES: {
                            **{h: v for h, v in cached.items() if h in hosts},
                            **devices,
                        },
                    },
                )
                return self.async_create_entry(
                    data={
                        # Hosts and auth mode live in entry.data; they are copied here so that
                        # changing only them still counts as an options change, which is what
                        # triggers OptionsFlowWithReload's reload.
                        CONF_HOSTS: hosts,
                        CONF_AUTH_MODE: auth_mode,
                        CONF_STATIONS: user_input.get(CONF_STATIONS, ""),
                        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    }
                )
        current = user_input or {
            CONF_HOSTS: "\n".join(entry.data[CONF_HOSTS]),
            CONF_AUTH_MODE: entry.data.get(CONF_AUTH_MODE, AUTH_STANDARD),
            CONF_STATIONS: entry.options.get(CONF_STATIONS, DEFAULT_STATIONS),
            CONF_SCAN_INTERVAL: entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        }
        schema = vol.Schema(
            {
                vol.Required(CONF_HOSTS): MULTILINE_SELECTOR,
                vol.Required(CONF_AUTH_MODE): AUTH_MODE_SELECTOR,
                vol.Optional(CONF_STATIONS): MULTILINE_SELECTOR,
                vol.Required(CONF_SCAN_INTERVAL): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=1,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, current),
            errors=errors,
            description_placeholders=placeholders,
        )
