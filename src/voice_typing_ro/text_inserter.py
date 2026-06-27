# Romanian Voice Typing Overlay
# Copyright (C) 2026 DrX-svg
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import ctypes
import logging
import time
from ctypes import wintypes
from dataclasses import dataclass

try:
    import keyboard as keyboard_lib
except ImportError:  # pragma: no cover - optional runtime dependency
    keyboard_lib = None


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

CF_UNICODETEXT = 13
GA_ROOT = 2
GMEM_MOVEABLE = 0x0002
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
SW_RESTORE = 9
VK_CONTROL = 0x11
VK_V = 0x56


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.WPARAM),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", _INPUTUNION),
    ]


LPINPUT = ctypes.POINTER(INPUT)

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SendInput.argtypes = [wintypes.UINT, LPINPUT, ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ULONG_PTR]
user32.keybd_event.restype = None
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.SetFocus.argtypes = [wintypes.HWND]
user32.SetFocus.restype = wintypes.HWND
user32.SetActiveWindow.argtypes = [wintypes.HWND]
user32.SetActiveWindow.restype = wintypes.HWND

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.restype = wintypes.HGLOBAL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


@dataclass(frozen=True)
class WindowTarget:
    hwnd: int
    title: str


@dataclass(frozen=True)
class PasteResult:
    success: bool
    status_text: str
    message: str
    target: WindowTarget | None
    used_window: WindowTarget | None
    restored_clipboard: bool
    invalidate_target: bool
    paste_mode: str
    clipboard_has_transcript: bool


class WindowsTextInserter:
    def __init__(
        self,
        logger: logging.Logger,
        restore_clipboard_after_paste: bool,
        paste_delay_ms: int,
    ) -> None:
        self.logger = logger
        self.restore_clipboard_after_paste = restore_clipboard_after_paste
        self.paste_delay_ms = paste_delay_ms

    def capture_foreground_window(
        self,
        exclude_hwnd: int | None = None,
    ) -> WindowTarget | None:
        hwnd = int(user32.GetForegroundWindow() or 0)
        if not hwnd:
            return None

        root_hwnd = int(user32.GetAncestor(hwnd, GA_ROOT) or hwnd)
        if exclude_hwnd and root_hwnd == exclude_hwnd:
            return None

        return WindowTarget(hwnd=root_hwnd, title=self.get_window_title(root_hwnd))

    def is_target_available(
        self,
        target: WindowTarget | None,
        overlay_hwnd: int | None = None,
    ) -> bool:
        if target is None:
            return False
        if overlay_hwnd and target.hwnd == overlay_hwnd:
            return False
        return bool(user32.IsWindow(target.hwnd))

    def describe_target(self, target: WindowTarget | None) -> str:
        if target is None:
            return "No target window"
        title = target.title.strip() or "Untitled window"
        return f"{self._format_hwnd(target.hwnd)} - {title}"

    def paste_text(
        self,
        text: str,
        target: WindowTarget | None,
        overlay_hwnd: int | None = None,
    ) -> PasteResult:
        transcript = text.strip()
        if not transcript:
            return PasteResult(
                success=False,
                status_text="No transcript to paste",
                message="Transcript is empty. Nothing to paste.",
                target=target,
                used_window=None,
                restored_clipboard=False,
                invalidate_target=False,
                paste_mode="none",
                clipboard_has_transcript=False,
            )

        invalidate_target = False
        if overlay_hwnd and target is not None and target.hwnd == overlay_hwnd:
            self.logger.warning("Captured target was the overlay window. Invalidating target.")
            target = None
            invalidate_target = True

        if target is not None and not user32.IsWindow(target.hwnd):
            self.logger.warning(
                "Captured target window is no longer valid. hwnd=%s",
                self._format_hwnd(target.hwnd),
            )
            target = None
            invalidate_target = True

        had_previous_text = False
        previous_text = ""
        try:
            had_previous_text, previous_text = self._get_clipboard_text()
        except Exception as exc:  # pragma: no cover - runtime-specific path
            self.logger.warning("Could not read clipboard text before paste: %s", exc)

        try:
            self._set_clipboard_text(transcript)
        except Exception as exc:  # pragma: no cover - runtime-specific path
            return PasteResult(
                success=False,
                status_text="Paste failed",
                message=f"Could not copy transcript to the clipboard: {exc}",
                target=target,
                used_window=None,
                restored_clipboard=False,
                invalidate_target=invalidate_target,
                paste_mode="none",
                clipboard_has_transcript=False,
            )

        clipboard_has_transcript = True
        time.sleep(self._clipboard_settle_delay_seconds())
        current_foreground = self.capture_foreground_window()
        self.logger.info(
            "Paste attempt. target=%s current_foreground=%s chars=%s",
            self.describe_target(target),
            self.describe_target(current_foreground),
            len(transcript),
        )

        if target is not None and current_foreground is not None and current_foreground.hwnd == target.hwnd:
            return self._paste_into_foreground_window(
                used_window=target,
                target=target,
                paste_mode="target",
                had_previous_text=had_previous_text,
                previous_text=previous_text,
                inserted_text=transcript,
                invalidate_target=invalidate_target,
            )

        if target is not None:
            focus_success = self._activate_target_window(target.hwnd, overlay_hwnd=overlay_hwnd)
            if focus_success:
                focused_window = self.capture_foreground_window()
                if focused_window is not None and focused_window.hwnd == target.hwnd:
                    return self._paste_into_foreground_window(
                        used_window=target,
                        target=target,
                        paste_mode="target",
                        had_previous_text=had_previous_text,
                        previous_text=previous_text,
                        inserted_text=transcript,
                        invalidate_target=invalidate_target,
                    )

        fallback_foreground = self.capture_foreground_window(exclude_hwnd=overlay_hwnd)
        if fallback_foreground is not None:
            return self._paste_into_foreground_window(
                used_window=fallback_foreground,
                target=target,
                paste_mode="active_window_fallback",
                had_previous_text=had_previous_text,
                previous_text=previous_text,
                inserted_text=transcript,
                invalidate_target=invalidate_target,
            )

        message = (
            "Paste failed, copied to clipboard. Press Ctrl+V manually."
        )
        self.logger.warning(
            "Paste fell back to clipboard-only. target=%s current_foreground=%s",
            self.describe_target(target),
            self.describe_target(current_foreground),
        )
        return PasteResult(
            success=False,
            status_text="Paste failed, copied to clipboard. Press Ctrl+V manually.",
            message=message,
            target=target,
            used_window=None,
            restored_clipboard=False,
            invalidate_target=invalidate_target,
            paste_mode="clipboard_only",
            clipboard_has_transcript=clipboard_has_transcript,
        )

    def get_window_title(self, hwnd: int) -> str:
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        return buffer.value

    def _paste_into_foreground_window(
        self,
        *,
        used_window: WindowTarget,
        target: WindowTarget | None,
        paste_mode: str,
        had_previous_text: bool,
        previous_text: str,
        inserted_text: str,
        invalidate_target: bool,
    ) -> PasteResult:
        current_foreground = self.capture_foreground_window()
        if current_foreground is None or current_foreground.hwnd != used_window.hwnd:
            self.logger.warning(
                "Foreground changed before paste. expected=%s actual=%s",
                self.describe_target(used_window),
                self.describe_target(current_foreground),
            )
            return PasteResult(
                success=False,
                status_text="Paste failed, copied to clipboard. Press Ctrl+V manually.",
                message=(
                    "Paste failed, copied to clipboard. Press Ctrl+V manually."
                ),
                target=target,
                used_window=current_foreground,
                restored_clipboard=False,
                invalidate_target=invalidate_target,
                paste_mode="clipboard_only",
                clipboard_has_transcript=True,
            )

        try:
            paste_method = self._send_paste_shortcut()
        except Exception as exc:  # pragma: no cover - runtime-specific path
            self.logger.warning("All paste send methods failed: %s", exc)
            return PasteResult(
                success=False,
                status_text="Paste failed, copied to clipboard. Press Ctrl+V manually.",
                message=(
                    f"Paste failed, copied to clipboard. Press Ctrl+V manually. Reason: {exc}"
                ),
                target=target,
                used_window=used_window,
                restored_clipboard=False,
                invalidate_target=invalidate_target,
                paste_mode="clipboard_only",
                clipboard_has_transcript=True,
            )

        time.sleep(self._delay_seconds())
        restored = self._restore_clipboard_if_safe(
            inserted_text,
            had_previous_text,
            previous_text,
        )

        if paste_mode == "target":
            status_text = "Pasted into target"
        else:
            status_text = "Pasted into active window fallback"

        self.logger.info(
            "Paste succeeded. mode=%s method=%s used_window=%s target=%s restored_clipboard=%s",
            paste_mode,
            paste_method,
            self.describe_target(used_window),
            self.describe_target(target),
            restored,
        )
        return PasteResult(
            success=True,
            status_text=status_text,
            message=f"{status_text}.",
            target=target,
            used_window=used_window,
            restored_clipboard=restored,
            invalidate_target=invalidate_target,
            paste_mode=paste_mode,
            clipboard_has_transcript=True,
        )

    def _activate_target_window(
        self,
        hwnd: int,
        overlay_hwnd: int | None = None,
    ) -> bool:
        target_window = WindowTarget(hwnd=hwnd, title=self.get_window_title(hwnd))
        before_foreground = self.capture_foreground_window()
        self.logger.info(
            "Attempting to focus target window. target=%s before_foreground=%s",
            self.describe_target(target_window),
            self.describe_target(before_foreground),
        )

        if self._basic_focus_attempt(hwnd):
            self.logger.info(
                "Focused target window with basic attempt. hwnd=%s",
                self._format_hwnd(hwnd),
            )
            return True

        if self._attached_focus_attempt(hwnd, before_foreground.hwnd if before_foreground else 0):
            self.logger.info(
                "Focused target window with AttachThreadInput attempt. hwnd=%s",
                self._format_hwnd(hwnd),
            )
            return True

        after_foreground = self.capture_foreground_window()
        if overlay_hwnd and after_foreground is not None and after_foreground.hwnd == overlay_hwnd:
            self.logger.warning(
                "Focus attempt left overlay in foreground. target=%s overlay=%s",
                self._format_hwnd(hwnd),
                self._format_hwnd(overlay_hwnd),
            )
        else:
            self.logger.warning(
                "Focus attempt failed. target=%s after_foreground=%s",
                self._format_hwnd(hwnd),
                self.describe_target(after_foreground),
            )
        return False

    def _basic_focus_attempt(self, hwnd: int) -> bool:
        ctypes.set_last_error(0)
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.BringWindowToTop(hwnd)
        set_result = user32.SetForegroundWindow(hwnd)
        last_error = ctypes.get_last_error()
        time.sleep(self._delay_seconds())
        success = int(user32.GetForegroundWindow() or 0) == hwnd
        if not success:
            self.logger.warning(
                "Basic SetForegroundWindow attempt failed. hwnd=%s set_result=%s last_error=%s",
                self._format_hwnd(hwnd),
                bool(set_result),
                last_error,
            )
        return success

    def _attached_focus_attempt(self, hwnd: int, foreground_hwnd: int) -> bool:
        current_thread_id = int(kernel32.GetCurrentThreadId())
        target_thread_id = self._get_window_thread_id(hwnd)
        foreground_thread_id = self._get_window_thread_id(foreground_hwnd) if foreground_hwnd else 0

        pairs_to_attach: list[tuple[int, int]] = []
        for first, second in [
            (current_thread_id, target_thread_id),
            (current_thread_id, foreground_thread_id),
            (foreground_thread_id, target_thread_id),
        ]:
            if not first or not second or first == second:
                continue
            pair = (first, second)
            if pair not in pairs_to_attach:
                pairs_to_attach.append(pair)

        attached_pairs: list[tuple[int, int]] = []
        try:
            for first, second in pairs_to_attach:
                ctypes.set_last_error(0)
                attached = user32.AttachThreadInput(first, second, True)
                last_error = ctypes.get_last_error()
                if attached:
                    attached_pairs.append((first, second))
                else:
                    self.logger.warning(
                        "AttachThreadInput failed. first_tid=%s second_tid=%s last_error=%s",
                        first,
                        second,
                        last_error,
                    )

            ctypes.set_last_error(0)
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.BringWindowToTop(hwnd)
            set_result = user32.SetForegroundWindow(hwnd)
            focus_result = user32.SetFocus(hwnd)
            active_result = user32.SetActiveWindow(hwnd)
            last_error = ctypes.get_last_error()
            time.sleep(self._delay_seconds())
            success = int(user32.GetForegroundWindow() or 0) == hwnd
            if not success:
                self.logger.warning(
                    "AttachThreadInput focus attempt failed. hwnd=%s set_result=%s focus_result=%s active_result=%s last_error=%s",
                    self._format_hwnd(hwnd),
                    bool(set_result),
                    bool(focus_result),
                    bool(active_result),
                    last_error,
                )
            return success
        finally:
            for first, second in reversed(attached_pairs):
                ctypes.set_last_error(0)
                detached = user32.AttachThreadInput(first, second, False)
                if not detached:
                    self.logger.warning(
                        "AttachThreadInput detach failed. first_tid=%s second_tid=%s last_error=%s",
                        first,
                        second,
                        ctypes.get_last_error(),
                    )

    def _get_window_thread_id(self, hwnd: int) -> int:
        process_id = wintypes.DWORD()
        return int(user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id)) or 0)

    def _send_paste_shortcut(self) -> str:
        if keyboard_lib is not None:
            try:
                keyboard_lib.press_and_release("ctrl+v")
                self.logger.info("Paste sent using keyboard.press_and_release")
                return "keyboard.press_and_release"
            except Exception as exc:  # pragma: no cover - runtime-specific path
                self.logger.warning("keyboard.press_and_release failed: %s", exc)
        else:
            self.logger.warning("keyboard.press_and_release unavailable: keyboard package not installed")

        try:
            self._send_ctrl_v_keybd_event()
            self.logger.info("Paste sent using keybd_event")
            return "keybd_event"
        except Exception as exc:  # pragma: no cover - runtime-specific path
            self.logger.warning("keybd_event paste fallback failed: %s", exc)

        try:
            self._send_ctrl_v_sendinput()
            self.logger.info("Paste sent using SendInput fallback")
            return "SendInput fallback"
        except Exception as exc:  # pragma: no cover - runtime-specific path
            self.logger.warning("SendInput paste fallback failed: %s", exc)
            raise RuntimeError(str(exc)) from exc

    def _send_ctrl_v_keybd_event(self) -> None:
        ctypes.set_last_error(0)
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_V, 0, 0, 0)
        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

    def _send_ctrl_v_sendinput(self) -> None:
        inputs = (INPUT * 4)(
            self._create_key_input(VK_CONTROL, 0),
            self._create_key_input(VK_V, 0),
            self._create_key_input(VK_V, KEYEVENTF_KEYUP),
            self._create_key_input(VK_CONTROL, KEYEVENTF_KEYUP),
        )
        ctypes.set_last_error(0)
        sent = user32.SendInput(len(inputs), inputs, ctypes.sizeof(INPUT))
        if sent != len(inputs):
            raise RuntimeError(
                f"SendInput did not send the full Ctrl+V sequence. last_error={ctypes.get_last_error()}"
            )

    def _create_key_input(self, virtual_key: int, flags: int) -> INPUT:
        input_item = INPUT()
        input_item.type = INPUT_KEYBOARD
        input_item.union.ki = KEYBDINPUT(
            wVk=virtual_key,
            wScan=0,
            dwFlags=flags,
            time=0,
            dwExtraInfo=0,
        )
        return input_item

    def _clipboard_settle_delay_seconds(self) -> float:
        return min(max(self.paste_delay_ms / 2000.0, 0.05), 0.1)

    def _delay_seconds(self) -> float:
        return max(self.paste_delay_ms, 0) / 1000.0

    def _get_clipboard_text(self) -> tuple[bool, str]:
        self._open_clipboard()
        try:
            if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                return False, ""

            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                raise RuntimeError("GetClipboardData returned no text handle.")

            locked = kernel32.GlobalLock(handle)
            if not locked:
                raise RuntimeError("GlobalLock failed for clipboard text.")

            try:
                return True, ctypes.wstring_at(locked)
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()

    def _set_clipboard_text(self, text: str) -> None:
        data = ctypes.create_unicode_buffer(text)
        size = ctypes.sizeof(data)
        memory_handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not memory_handle:
            raise RuntimeError("GlobalAlloc failed for clipboard text.")

        locked = kernel32.GlobalLock(memory_handle)
        if not locked:
            kernel32.GlobalFree(memory_handle)
            raise RuntimeError("GlobalLock failed for clipboard text.")

        try:
            ctypes.memmove(locked, data, size)
        finally:
            kernel32.GlobalUnlock(memory_handle)

        self._open_clipboard()
        try:
            if not user32.EmptyClipboard():
                raise RuntimeError("EmptyClipboard failed.")

            if not user32.SetClipboardData(CF_UNICODETEXT, memory_handle):
                raise RuntimeError("SetClipboardData failed.")
            memory_handle = None
        finally:
            user32.CloseClipboard()
            if memory_handle:
                kernel32.GlobalFree(memory_handle)

    def _restore_clipboard_if_safe(
        self,
        inserted_text: str,
        had_previous_text: bool,
        previous_text: str,
    ) -> bool:
        if not self.restore_clipboard_after_paste or not had_previous_text:
            return False

        try:
            has_current_text, current_text = self._get_clipboard_text()
        except Exception as exc:  # pragma: no cover - runtime-specific path
            self.logger.warning("Could not inspect clipboard before restore: %s", exc)
            return False

        if not has_current_text or current_text != inserted_text:
            return False

        try:
            self._set_clipboard_text(previous_text)
        except Exception as exc:  # pragma: no cover - runtime-specific path
            self.logger.warning("Could not restore clipboard text after paste: %s", exc)
            return False
        return True

    def _open_clipboard(self) -> None:
        for _ in range(10):
            if user32.OpenClipboard(None):
                return
            time.sleep(0.05)
        raise RuntimeError("OpenClipboard failed after multiple retries.")

    def _format_hwnd(self, hwnd: int) -> str:
        return f"0x{hwnd:08X}"
