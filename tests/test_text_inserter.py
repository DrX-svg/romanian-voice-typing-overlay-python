import sys
from unittest.mock import Mock

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="text_inserter imports Windows clipboard APIs")
def test_open_clipboard_failure_frees_allocation(monkeypatch):
    from voice_typing_ro import text_inserter as module

    kernel = Mock()
    kernel.GlobalAlloc.return_value = 123
    kernel.GlobalLock.return_value = 456
    user = Mock()
    monkeypatch.setattr(module, "kernel32", kernel)
    monkeypatch.setattr(module, "user32", user)
    monkeypatch.setattr(module.ctypes, "memmove", Mock())
    inserter = module.WindowsTextInserter.__new__(module.WindowsTextInserter)
    inserter._open_clipboard = Mock(side_effect=RuntimeError("OpenClipboard failed"))
    with pytest.raises(RuntimeError, match="OpenClipboard failed"):
        inserter._set_clipboard_text("test")
    kernel.GlobalFree.assert_called_once_with(123)
    user.CloseClipboard.assert_not_called()
