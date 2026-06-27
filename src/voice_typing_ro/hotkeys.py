# Romanian Voice Typing Overlay
# Copyright (C) 2026 DrX-svg
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

try:
    import keyboard as keyboard_lib
except ImportError:  # pragma: no cover - optional runtime dependency
    keyboard_lib = None


@dataclass(frozen=True)
class HotkeyRegistrationResult:
    registered: bool
    message: str
    active_hotkey: str
    active_display_hotkey: str


def format_hotkey(hotkey: str) -> str:
    parts = []
    for part in hotkey.split("+"):
        cleaned = part.strip()
        if len(cleaned) == 1:
            parts.append(cleaned.upper())
        else:
            parts.append(cleaned.title())
    return " + ".join(parts)


class GlobalHotkeyManager:
    def __init__(
        self,
        hotkey: str,
        logger: logging.Logger,
        callback: Callable[[], None],
    ) -> None:
        self.hotkey = hotkey
        self.display_hotkey = format_hotkey(hotkey)
        self.logger = logger
        self.callback = callback
        self._hotkey_handle = None

    @property
    def current_hotkey(self) -> str:
        return self.hotkey

    def register(self) -> HotkeyRegistrationResult:
        return self.register_hotkey(self.hotkey)

    def register_hotkey(
        self,
        hotkey_string: str,
        callback: Callable[[], None] | None = None,
    ) -> HotkeyRegistrationResult:
        normalized_hotkey = hotkey_string.strip().lower()
        requested_display_hotkey = format_hotkey(normalized_hotkey)
        if not normalized_hotkey:
            return HotkeyRegistrationResult(
                registered=False,
                message="Hotkey cannot be empty.",
                active_hotkey=self.hotkey,
                active_display_hotkey=self.display_hotkey,
            )

        if callback is not None:
            self.callback = callback

        if self._hotkey_handle is not None:
            return HotkeyRegistrationResult(
                registered=True,
                message=f"Hotkey already registered: {self.display_hotkey}",
                active_hotkey=self.hotkey,
                active_display_hotkey=self.display_hotkey,
            )

        if keyboard_lib is None:
            message = (
                f"Failed to register {requested_display_hotkey}. "
                "Install the keyboard package first."
            )
            self.logger.error(message)
            return HotkeyRegistrationResult(
                registered=False,
                message=message,
                active_hotkey=self.hotkey,
                active_display_hotkey=self.display_hotkey,
            )

        try:
            hotkey_handle = keyboard_lib.add_hotkey(
                normalized_hotkey,
                self._invoke_callback,
                suppress=False,
                trigger_on_release=False,
            )
        except Exception as exc:  # pragma: no cover - runtime-specific path
            message = f"Failed to register {requested_display_hotkey}: {exc}"
            self.logger.error(message)
            return HotkeyRegistrationResult(
                registered=False,
                message=message,
                active_hotkey=self.hotkey,
                active_display_hotkey=self.display_hotkey,
            )

        self._hotkey_handle = hotkey_handle
        self.hotkey = normalized_hotkey
        self.display_hotkey = requested_display_hotkey
        self.logger.info("Hotkey registered: %s", self.display_hotkey)
        return HotkeyRegistrationResult(
            registered=True,
            message=f"Registered {self.display_hotkey}",
            active_hotkey=self.hotkey,
            active_display_hotkey=self.display_hotkey,
        )

    def unregister_current_hotkey(self) -> None:
        if self._hotkey_handle is None or keyboard_lib is None:
            return

        try:
            keyboard_lib.remove_hotkey(self._hotkey_handle)
            self.logger.info("Hotkey unregistered: %s", self.display_hotkey)
        except Exception as exc:  # pragma: no cover - runtime-specific path
            self.logger.warning(
                "Failed to unregister hotkey %s: %s",
                self.display_hotkey,
                exc,
            )
        finally:
            self._hotkey_handle = None

    def unregister(self) -> None:
        self.unregister_current_hotkey()

    def reregister_hotkey(self, new_hotkey_string: str) -> HotkeyRegistrationResult:
        normalized_hotkey = new_hotkey_string.strip().lower()
        if not normalized_hotkey:
            return HotkeyRegistrationResult(
                registered=False,
                message="Hotkey cannot be empty.",
                active_hotkey=self.hotkey,
                active_display_hotkey=self.display_hotkey,
            )

        previous_hotkey = self.hotkey
        previous_display = self.display_hotkey
        had_registered_hotkey = self._hotkey_handle is not None

        if had_registered_hotkey:
            self.unregister_current_hotkey()

        result = self.register_hotkey(normalized_hotkey)
        if result.registered:
            return result

        self.hotkey = previous_hotkey
        self.display_hotkey = previous_display

        if had_registered_hotkey:
            restore_result = self.register_hotkey(previous_hotkey)
            if restore_result.registered:
                message = (
                    f"Failed to register {format_hotkey(normalized_hotkey)}. "
                    f"Restored {previous_display}."
                )
                self.logger.warning(message)
                return HotkeyRegistrationResult(
                    registered=False,
                    message=message,
                    active_hotkey=self.hotkey,
                    active_display_hotkey=self.display_hotkey,
                )

            message = (
                f"Failed to register {format_hotkey(normalized_hotkey)}. "
                f"Restoring {previous_display} also failed: {restore_result.message}"
            )
            self.logger.error(message)
            return HotkeyRegistrationResult(
                registered=False,
                message=message,
                active_hotkey=self.hotkey,
                active_display_hotkey=self.display_hotkey,
            )

        return HotkeyRegistrationResult(
            registered=False,
            message=result.message,
            active_hotkey=self.hotkey,
            active_display_hotkey=self.display_hotkey,
        )

    def _invoke_callback(self) -> None:
        self.logger.info("Hotkey pressed: %s", self.display_hotkey)
        try:
            self.callback()
        except Exception:  # pragma: no cover - defensive logging
            self.logger.exception(
                "Unhandled exception while processing hotkey %s.",
                self.display_hotkey,
            )
