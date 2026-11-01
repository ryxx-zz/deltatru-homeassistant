"""Config flow: sign in to the DeltaTru cloud; ESPHome zeroconf just starts it."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import DeltaTruAuthError, DeltaTruClient, DeltaTruError
from .const import (
    CONF_ANON_KEY,
    CONF_DASHBOARD,
    CONF_DEVICE_MAP,
    CONF_NOTIFY,
    CONF_REFRESH_TOKEN,
    CONF_SUPABASE_URL,
    CONF_USER_ID,
    DEFAULT_ANON_KEY,
    DEFAULT_SUPABASE_URL,
    DOMAIN,
)
from .discovery import find_monitors

UNASSIGNED = "auto"


def _schema(defaults: Mapping[str, Any], ask_key: bool) -> vol.Schema:
    fields: dict[Any, Any] = {
        vol.Required(CONF_EMAIL, default=defaults.get(CONF_EMAIL, "")): str,
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
    if ask_key:
        fields[vol.Required(CONF_ANON_KEY, default=defaults.get(CONF_ANON_KEY, ""))] = str
        fields[vol.Required(CONF_SUPABASE_URL, default=defaults.get(CONF_SUPABASE_URL, DEFAULT_SUPABASE_URL))] = str
    return vol.Schema(fields)


class DeltaTruConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _sign_in(self, user_input: dict[str, Any]) -> tuple[DeltaTruClient | None, dict[str, str]]:
        client = DeltaTruClient(
            async_get_clientsession(self.hass),
            user_input.get(CONF_SUPABASE_URL, DEFAULT_SUPABASE_URL),
            user_input.get(CONF_ANON_KEY, DEFAULT_ANON_KEY),
        )
        try:
            await client.async_sign_in(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
        except DeltaTruAuthError:
            return None, {"base": "invalid_auth"}
        except DeltaTruError:
            return None, {"base": "cannot_connect"}
        return client, {}

    def _data(self, user_input: dict[str, Any], client: DeltaTruClient) -> dict[str, Any]:
        return {
            CONF_EMAIL: user_input[CONF_EMAIL],
            CONF_SUPABASE_URL: user_input.get(CONF_SUPABASE_URL, DEFAULT_SUPABASE_URL),
            CONF_ANON_KEY: user_input.get(CONF_ANON_KEY, DEFAULT_ANON_KEY),
            CONF_REFRESH_TOKEN: client.refresh_token,
            CONF_USER_ID: client.user_id,
        }

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            client, errors = await self._sign_in(user_input)
            if client:
                await self.async_set_unique_id(client.user_id or user_input[CONF_EMAIL].lower(), raise_on_progress=False)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input[CONF_EMAIL], data=self._data(user_input, client))
        found = len(find_monitors(self.hass))
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input or {}, not DEFAULT_ANON_KEY),
            errors=errors,
            description_placeholders={"found": str(found)},
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """A DeltaTru monitor announced itself; offer setup once per HA."""
        await self.async_set_unique_id(DOMAIN + "_discovery")
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"name": discovery_info.properties.get("friendly_name", discovery_info.name.split(".")[0])}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="zeroconf_confirm", description_placeholders=self.context["title_placeholders"])
        return await self.async_step_user()

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            merged = {**entry.data, **user_input}
            client, errors = await self._sign_in(merged)
            if client:
                return self.async_update_reload_and_abort(entry, data=self._data(merged, client))
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_schema(entry.data, False),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return DeltaTruOptionsFlow()


class DeltaTruOptionsFlow(OptionsFlowWithReload):
    """Dashboard / notification toggles and manual monitor→system mapping."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.config_entry
        systems = {sid: s.name for sid, s in (entry.runtime_data.data or {}).items()} if hasattr(entry, "runtime_data") else {}
        monitors = find_monitors(self.hass)
        current = entry.options.get(CONF_DEVICE_MAP, {})
        if user_input is not None:
            device_map = {
                m.device_id: user_input[m.device_id]
                for m in monitors
                if user_input.get(m.device_id, UNASSIGNED) != UNASSIGNED
            }
            return self.async_create_entry(data={
                CONF_DASHBOARD: user_input[CONF_DASHBOARD],
                CONF_NOTIFY: user_input[CONF_NOTIFY],
                CONF_DEVICE_MAP: device_map,
            })
        choices = [selector.SelectOptionDict(value=UNASSIGNED, label="Automatic")] + [
            selector.SelectOptionDict(value=sid, label=name) for sid, name in systems.items()
        ]
        fields: dict[Any, Any] = {
            vol.Required(CONF_DASHBOARD, default=entry.options.get(CONF_DASHBOARD, True)): bool,
            vol.Required(CONF_NOTIFY, default=entry.options.get(CONF_NOTIFY, True)): bool,
        }
        for m in monitors:
            fields[vol.Optional(m.device_id, default=current.get(m.device_id, UNASSIGNED),
                                description={"suggested_value": current.get(m.device_id, UNASSIGNED)})] = (
                selector.SelectSelector(selector.SelectSelectorConfig(options=choices, mode=selector.SelectSelectorMode.DROPDOWN))
            )
        names = ", ".join(f"{m.name} ({m.role})" for m in monitors) or "none"
        return self.async_show_form(step_id="init", data_schema=vol.Schema(fields), description_placeholders={"monitors": names})
