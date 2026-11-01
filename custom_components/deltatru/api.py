"""Minimal read-only client for the DeltaTru cloud (Supabase auth + PostgREST)."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp


class DeltaTruError(Exception):
    """Generic cloud error."""


class DeltaTruAuthError(DeltaTruError):
    """Credentials or refresh token rejected."""


class DeltaTruClient:
    """Talks to Supabase with the user's own session; RLS scopes all reads."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        anon_key: str,
        refresh_token: str | None = None,
    ) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._key = anon_key
        self.refresh_token = refresh_token
        self._access_token: str | None = None
        self.user_id: str | None = None
        self._lock = asyncio.Lock()

    async def _auth(self, grant: str, body: dict[str, Any]) -> None:
        try:
            resp = await self._session.post(
                f"{self._url}/auth/v1/token",
                params={"grant_type": grant},
                json=body,
                headers={"apikey": self._key},
                timeout=aiohttp.ClientTimeout(total=20),
            )
            data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise DeltaTruError(str(err)) from err
        if resp.status in (400, 401, 403):
            raise DeltaTruAuthError(str(data.get("error_description") or data.get("msg") or data))
        if resp.status >= 300:
            raise DeltaTruError(f"auth HTTP {resp.status}")
        self._access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.user_id = (data.get("user") or {}).get("id")

    async def async_sign_in(self, email: str, password: str) -> None:
        """Password sign-in (same as the web dashboard)."""
        await self._auth("password", {"email": email, "password": password})

    async def async_refresh(self) -> None:
        """Exchange the stored refresh token for a fresh access token."""
        if not self.refresh_token:
            raise DeltaTruAuthError("no refresh token")
        await self._auth("refresh_token", {"refresh_token": self.refresh_token})

    async def _get(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        async with self._lock:
            if self._access_token is None:
                await self.async_refresh()
        for attempt in (0, 1):
            try:
                resp = await self._session.get(
                    f"{self._url}/rest/v1/{table}",
                    params=params,
                    headers={
                        "apikey": self._key,
                        "Authorization": f"Bearer {self._access_token}",
                    },
                    timeout=aiohttp.ClientTimeout(total=20),
                )
                if resp.status == 401 and attempt == 0:
                    async with self._lock:
                        await self.async_refresh()
                    continue
                if resp.status >= 300:
                    raise DeltaTruError(f"{table} HTTP {resp.status}")
                return await resp.json(content_type=None)
            except (aiohttp.ClientError, TimeoutError) as err:
                raise DeltaTruError(str(err)) from err
        raise DeltaTruAuthError("session expired")

    async def async_systems(self) -> list[dict[str, Any]]:
        return await self._get("systems", {"select": "id,name,status", "order": "name"})

    async def async_devices(self) -> list[dict[str, Any]]:
        return await self._get(
            "devices",
            {"select": "device_id,role,system_id,last_seen_at,last_rssi,fw_version,status"},
        )

    async def async_active_alerts(self) -> list[dict[str, Any]]:
        return await self._get(
            "alerts",
            {
                "select": "id,system_id,rule_id,family,severity,status,title,first_seen,last_seen",
                "status": "in.(open,acknowledged)",
                "order": "last_seen.desc",
            },
        )
