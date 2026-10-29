import logging
from unittest.mock import Mock, call

from voice_typing_ro.hotkeys import GlobalHotkeyManager, format_hotkey


def test_format_hotkey():
    assert format_hotkey("ctrl + shift + a") == "Ctrl + Shift + A"
    assert format_hotkey("f10") == "F10"


def test_register_and_unregister(fake_keyboard):
    callback = Mock()
    manager = GlobalHotkeyManager("f10", logging.getLogger("test"), callback)
    result = manager.register()
    assert result.registered
    assert result.active_hotkey == "f10"
    fake_keyboard.add_hotkey.assert_called_once_with("f10", manager._invoke_callback, suppress=False, trigger_on_release=False)
    fake_keyboard.add_hotkey.call_args.args[1]()
    callback.assert_called_once_with()
    manager.unregister()
    fake_keyboard.remove_hotkey.assert_called_once_with(fake_keyboard.add_hotkey.return_value)
    manager.unregister()
    assert fake_keyboard.remove_hotkey.call_count == 1


def test_reregister_success(fake_keyboard):
    fake_keyboard.add_hotkey.side_effect = ["old", "new"]
    manager = GlobalHotkeyManager("f10", logging.getLogger("test"), Mock())
    manager.register()
    result = manager.reregister_hotkey(" CTRL+F9 ")
    assert result.registered
    assert manager.current_hotkey == "ctrl+f9"
    fake_keyboard.remove_hotkey.assert_called_once_with("old")
    manager.unregister()
    assert fake_keyboard.remove_hotkey.call_args == call("new")


def test_reregister_failure_restores_previous_hotkey(fake_keyboard):
    fake_keyboard.add_hotkey.side_effect = ["old", RuntimeError("invalid"), "restored"]
    manager = GlobalHotkeyManager("f10", logging.getLogger("test"), Mock())
    manager.register()
    result = manager.reregister_hotkey("invalid")
    assert not result.registered
    assert result.active_hotkey == manager.current_hotkey == "f10"
    assert result.active_display_hotkey == "F10"
    assert [entry.args[0] for entry in fake_keyboard.add_hotkey.call_args_list] == ["f10", "invalid", "f10"]
    manager.unregister()
    assert fake_keyboard.remove_hotkey.call_args == call("restored")
