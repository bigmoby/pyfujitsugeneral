"""Fujitsu General API Client."""

import asyncio
import json
import logging
import os
import socket
from typing import Any

import aiofiles
import aiohttp

from pyfujitsugeneral.exceptions import FGLairGeneralException
from pyfujitsugeneral.utils import isBlank

TIMEOUT = 10
HEADER_CONTENT_TYPE = "Content-Type"
HEADER_VALUE_CONTENT_TYPE = "application/json"
HEADER_AUTHORIZATION = "Authorization"

_LOGGER: logging.Logger = logging.getLogger(__package__)


def api_headers(access_token: str | None = None) -> dict[str, str]:
    headers = {HEADER_CONTENT_TYPE: HEADER_VALUE_CONTENT_TYPE}
    if access_token:
        headers[HEADER_AUTHORIZATION] = "auth_token " + access_token
    return headers


class FGLairApiClient:
    def __init__(
        self,
        username: str,
        password: str,
        region: str,
        tokenpath: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """FGLairApiClient API Client."""
        self._username = username
        self._password = password
        self._region = region
        self._tokenpath = tokenpath
        self._session = session

        if region == "eu":
            app_id = "FGLair-eu-id"
            app_secret = "FGLair-eu-gpFbVBRoiJ8E3QWJ-QRULLL3j3U"
            self._API_GET_ACCESS_TOKEN_URL = (
                "https://user-field-eu.aylanetworks.com/users/sign_in.json"
            )
            API_BASE_URL = "https://ads-field-eu.aylanetworks.com/apiv1/"
        elif region == "cn":
            app_id = "FGLairField-cn-id"
            app_secret = "FGLairField-cn-zezg7Y60YpAvy3HPwxvWLnd4Oh4"
            self._API_GET_ACCESS_TOKEN_URL = (
                "https://user-field.ayla.com.cn/users/sign_in.json"
            )
            API_BASE_URL = "https://ads-field.ayla.com.cn/apiv1/"
        else:
            app_id = "CJIOSP-id"
            app_secret = "CJIOSP-Vb8MQL_lFiYQ7DKjN0eCFXznKZE"
            self._API_GET_ACCESS_TOKEN_URL = (
                "https://user-field.aylanetworks.com/users/sign_in.json"
            )
            API_BASE_URL = "https://ads-field.aylanetworks.com/apiv1/"

        self._SIGNIN_BODY = json.dumps(
            {
                "user": {
                    "email": self._username,
                    "password": self._password,
                    "application": {
                        "app_id": app_id,
                        "app_secret": app_secret,
                    },
                }
            }
        )
        self._API_GET_PROPERTIES_URL = API_BASE_URL + "dsns/{DSN}/properties.json"
        self._API_SET_PROPERTIES_URL = (
            API_BASE_URL + "properties/{property}/datapoints.json"
        )
        self._API_GET_DEVICES_URL = API_BASE_URL + "devices.json"
        self._ACCESS_TOKEN_FILE = tokenpath
        self._ACCESS_TOKEN_STR = None

    @staticmethod
    def _api_error_message(response: Any) -> str | None:
        if not isinstance(response, dict):
            return None

        error = response.get("error")
        if not error:
            return None

        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message")
            if code and message:
                return f"{code} - {message}"
            if message:
                return str(message)
            if code:
                return str(code)

        return str(error)

    async def _async_read_token(self, access_token_file: str = "") -> str:
        if isBlank(access_token_file):
            access_token_file = self._ACCESS_TOKEN_FILE

        if (
            os.path.exists(access_token_file)
            and os.stat(access_token_file).st_size != 0
        ):
            try:
                async with aiofiles.open(access_token_file, encoding="utf-8") as f:
                    access_token_file_content = await f.read()
                access_token = json.loads(access_token_file_content).get("access_token")
                if access_token:
                    return str(access_token)
            except (json.JSONDecodeError, TypeError, OSError) as exception:
                _LOGGER.warning(
                    "Unable to read cached FGLair access token from %s - %s",
                    access_token_file,
                    exception,
                )

        return await self.async_authenticate()

    async def _async_get_devices(self, access_token: str | None = None) -> Any:
        if not access_token:
            access_token = await self._async_read_token()

        try:
            response_json = await self.api_wrapper(
                "get", self._API_GET_DEVICES_URL, access_token=access_token
            )
        except FGLairGeneralException:
            access_token = await self.async_authenticate()
            response_json = await self.api_wrapper(
                "get", self._API_GET_DEVICES_URL, access_token=access_token
            )

        if api_error := self._api_error_message(response_json):
            _LOGGER.error(
                "FGLair API returned an error while fetching devices: %s",
                api_error,
            )
            raise FGLairGeneralException

        if not isinstance(response_json, list):
            _LOGGER.error(
                "Unexpected FGLair devices response type: %s",
                type(response_json).__name__,
            )
            raise FGLairGeneralException

        return response_json

    async def async_get_devices_dsn(self) -> list[str]:
        devices = await self._async_get_devices()
        devices_dsn: list[str] = []

        for device in devices:
            try:
                dsn = device["device"]["dsn"]
            except (KeyError, TypeError) as exception:
                _LOGGER.error(
                    "Unexpected FGLair device entry while parsing DSN: %s",
                    device,
                )
                raise FGLairGeneralException from exception

            if not dsn:
                _LOGGER.error("FGLair device entry does not contain a DSN: %s", device)
                raise FGLairGeneralException

            devices_dsn.append(str(dsn))

        return devices_dsn

    async def async_get_device_property(self, property_code: int) -> Any:
        access_token = await self._async_read_token()
        try:
            return await self.api_wrapper(
                "get",
                self._API_SET_PROPERTIES_URL.format(property=property_code),
                access_token=access_token,
            )
        except FGLairGeneralException:
            access_token = await self.async_authenticate()
            return await self.api_wrapper(
                "get",
                self._API_SET_PROPERTIES_URL.format(property=property_code),
                access_token=access_token,
            )

    async def async_get_device_properties(self, dsn: str) -> Any:
        access_token = await self._async_read_token()
        try:
            return await self.api_wrapper(
                "get",
                url=self._API_GET_PROPERTIES_URL.format(DSN=dsn),
                access_token=access_token,
            )
        except FGLairGeneralException:
            access_token = await self.async_authenticate()
            return await self.api_wrapper(
                "get",
                url=self._API_GET_PROPERTIES_URL.format(DSN=dsn),
                access_token=access_token,
            )

    async def async_set_device_property(self, property_code: int, value: Any) -> Any:
        access_token = await self._async_read_token()
        json_data = json.dumps({"datapoint": {"value": str(value)}})
        try:
            return await self.api_wrapper(
                "post",
                url=self._API_SET_PROPERTIES_URL.format(property=property_code),
                json_data=json_data,
                access_token=access_token,
            )
        except FGLairGeneralException:
            access_token = await self.async_authenticate()
            return await self.api_wrapper(
                "post",
                url=self._API_SET_PROPERTIES_URL.format(property=property_code),
                json_data=json_data,
                access_token=access_token,
            )

    async def _async_check_token_validity(
        self, access_token: str | None = None
    ) -> bool:
        if not access_token:
            return False

        try:
            response = await self.api_wrapper(
                method="get",
                url=self._API_GET_DEVICES_URL,
                access_token=access_token,
            )
            if self._api_error_message(response):
                return False
            return isinstance(response, list)
        except FGLairGeneralException:
            return False

    async def async_authenticate(self) -> str:
        response = await self.api_wrapper(
            "post",
            url=self._API_GET_ACCESS_TOKEN_URL,
            json_data=self._SIGNIN_BODY,
        )

        if api_error := self._api_error_message(response):
            _LOGGER.error("FGLair authentication failed: %s", api_error)
            raise FGLairGeneralException

        if not isinstance(response, dict):
            _LOGGER.error(
                "Unexpected FGLair authentication response type: %s",
                type(response).__name__,
            )
            raise FGLairGeneralException

        access_token = response.get("access_token")
        if not access_token:
            _LOGGER.error("FGLair authentication response did not include access_token")
            raise FGLairGeneralException

        async with aiofiles.open(
            self._ACCESS_TOKEN_FILE, mode="w", encoding="utf-8"
        ) as f:
            await f.write(json.dumps(response))

        self._ACCESS_TOKEN_STR = access_token
        return str(access_token)

    async def api_wrapper(
        self,
        method: str,
        url: str,
        json_data: str = "",
        access_token: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Get information from the API."""
        try:
            if not headers:
                headers = api_headers(access_token=access_token)

            async with asyncio.timeout(TIMEOUT):
                if method == "get":
                    request = self._session.get(url, headers=headers)
                elif method == "post":
                    request = self._session.post(url, headers=headers, data=json_data)
                else:
                    raise FGLairGeneralException

                async with request as response:
                    response.raise_for_status()
                    return await response.json()

        except TimeoutError as exception:
            _LOGGER.error(
                "Timeout error fetching information from %s - %s",
                url,
                exception,
            )
            raise FGLairGeneralException from exception
        except aiohttp.ContentTypeError as exception:
            _LOGGER.error(
                "Error decoding JSON while fetching information from %s - %s",
                url,
                exception,
            )
            raise FGLairGeneralException from exception
        except (KeyError, TypeError) as exception:
            _LOGGER.error(
                "Error parsing information from %s - %s",
                url,
                exception,
            )
            raise FGLairGeneralException from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            _LOGGER.error(
                "Error fetching information from %s - %s",
                url,
                exception,
            )
            raise FGLairGeneralException from exception
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("Something really wrong happened! - %s", exception)
            raise FGLairGeneralException from exception
