# Romanian Voice Typing Overlay
# Copyright (C) 2026 DrX-svg
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk

from .settings import AppSettings


LIGHT_PALETTE = {
    "root_bg": "#f7f7f7",
    "frame_bg": "#ffffff",
    "fg": "#202020",
    "muted_fg": "#5d5d5d",
    "input_bg": "#ffffff",
    "input_fg": "#111111",
    "button_bg": "#ececec",
    "button_active_bg": "#dfdfdf",
    "border": "#c8c8c8",
    "selection_bg": "#cfe8ff",
    "disabled_fg": "#8a8a8a",
}

DARK_PALETTE = {
    "root_bg": "#1e1e1e",
    "frame_bg": "#252526",
    "fg": "#f0f0f0",
    "muted_fg": "#c8c8c8",
    "input_bg": "#111111",
    "input_fg": "#ffffff",
    "button_bg": "#333333",
    "button_active_bg": "#404040",
    "border": "#3c3c3c",
    "selection_bg": "#264f78",
    "disabled_fg": "#7d7d7d",
}


class VoiceTypingOverlay:
    def __init__(
        self,
        root: tk.Tk,
        settings: AppSettings,
        on_start_recording,
        on_stop_transcribe,
        on_clear,
        on_copy,
        on_paste,
        on_change_hotkey,
        on_refresh_microphones,
        on_microphone_selected,
        on_toggle_advanced_devices,
        on_asr_preset_selected,
        on_opacity_changed,
        on_dark_mode_toggled,
    ) -> None:
        self.root = root
        self.settings = settings
        self.on_start_recording = on_start_recording
        self.on_stop_transcribe = on_stop_transcribe
        self.on_clear = on_clear
        self.on_copy = on_copy
        self.on_paste = on_paste
        self.on_change_hotkey = on_change_hotkey
        self.on_refresh_microphones = on_refresh_microphones
        self.on_microphone_selected = on_microphone_selected
        self.on_toggle_advanced_devices = on_toggle_advanced_devices
        self.on_asr_preset_selected = on_asr_preset_selected
        self.on_opacity_changed = on_opacity_changed
        self.on_dark_mode_toggled = on_dark_mode_toggled

        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")
        self._dark_mode_enabled = False

        self.status_var = tk.StringVar(value="Status: Loading model")
        self.hotkey_var = tk.StringVar(value="Hotkey: Registering...")
        self.target_var = tk.StringVar(value="Target: No target window captured.")
        self.microphone_var = tk.StringVar(value="")
        self.show_advanced_devices_var = tk.BooleanVar(value=False)
        self.asr_preset_var = tk.StringVar(value="balanced")
        self.asr_summary_var = tk.StringVar(value="Balanced")
        self.opacity_percent_var = tk.DoubleVar(value=100.0)
        self.opacity_summary_var = tk.StringVar(value="Opacity: 100%")
        self.view_summary_var = tk.StringVar(value="Light | 100%")
        self.dark_mode_var = tk.BooleanVar(value=False)
        self._side_panel: tk.Toplevel | None = None
        self._side_panel_kind: str | None = None

        self._build_window()
        self._build_widgets()
        self._apply_theme()

    def _build_window(self) -> None:
        self.root.title(self.settings.window_title)
        self.root.geometry(self.settings.window_geometry)
        self.root.attributes("-topmost", self.settings.always_on_top)
        self.root.attributes("-alpha", self.settings.window_opacity)
        self.root.resizable(True, True)
        self.root.minsize(520, 420)

    def _build_widgets(self) -> None:
        self.container = ttk.Frame(self.root, padding=12, style="Root.TFrame")
        self.container.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.container.columnconfigure(0, weight=1)
        self.container.rowconfigure(6, weight=1)

        status_label = ttk.Label(
            self.container,
            textvariable=self.status_var,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
            justify="left",
            style="Root.TLabel",
        )
        status_label.grid(row=0, column=0, sticky="ew")

        settings_frame = ttk.LabelFrame(
            self.container,
            text="Settings",
            padding=10,
            style="Settings.TLabelframe",
        )
        settings_frame.grid(row=1, column=0, sticky="ew", pady=(8, 8))
        settings_frame.columnconfigure(0, weight=1)

        settings_content = ttk.Frame(settings_frame, style="SettingsBody.TFrame")
        settings_content.grid(row=0, column=0, sticky="ew")
        settings_content.columnconfigure(1, weight=1)

        settings_actions = ttk.Frame(settings_frame, style="SettingsBody.TFrame")
        settings_actions.grid(row=0, column=1, sticky="ne", padx=(10, 0))
        settings_actions.columnconfigure(0, weight=1)

        hotkey_title_label = ttk.Label(
            settings_content,
            text="Hotkey",
            style="SettingsBody.TLabel",
        )
        hotkey_title_label.grid(row=0, column=0, sticky="w")

        hotkey_label = ttk.Label(
            settings_content,
            textvariable=self.hotkey_var,
            anchor="w",
            justify="left",
            style="SettingsBody.TLabel",
        )
        hotkey_label.grid(row=0, column=1, sticky="ew", padx=(8, 8))

        self.change_hotkey_button = ttk.Button(
            settings_content,
            text="Change Hotkey",
            command=self.on_change_hotkey,
            style="Overlay.TButton",
        )
        self.change_hotkey_button.grid(row=0, column=2, sticky="e")

        microphone_title_label = ttk.Label(
            settings_content,
            text="Microphone",
            style="SettingsBody.TLabel",
        )
        microphone_title_label.grid(row=1, column=0, sticky="w", pady=(8, 0))

        self.microphone_combo = ttk.Combobox(
            settings_content,
            textvariable=self.microphone_var,
            state="readonly",
            style="Overlay.TCombobox",
        )
        self.microphone_combo.grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        self.microphone_combo.bind("<<ComboboxSelected>>", self._handle_microphone_selected)

        self.refresh_microphones_button = ttk.Button(
            settings_content,
            text="Refresh Microphones",
            command=self.on_refresh_microphones,
            style="Overlay.TButton",
        )
        self.refresh_microphones_button.grid(row=1, column=2, sticky="e", pady=(8, 0))

        self.show_advanced_devices_checkbutton = ttk.Checkbutton(
            settings_content,
            text="Show advanced devices",
            variable=self.show_advanced_devices_var,
            command=self._handle_show_advanced_devices_toggle,
            style="SettingsBody.TCheckbutton",
        )
        self.show_advanced_devices_checkbutton.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(8, 0),
        )

        self.view_panel_button = ttk.Button(
            settings_actions,
            text="View >",
            width=9,
            command=self.toggle_view_panel,
            style="Overlay.TButton",
        )
        self.view_panel_button.grid(row=0, column=0, sticky="ew")

        view_summary_label = ttk.Label(
            settings_actions,
            textvariable=self.view_summary_var,
            anchor="e",
            justify="right",
            style="SettingsDetail.TLabel",
        )
        view_summary_label.grid(row=1, column=0, sticky="e", pady=(4, 8))

        self.asr_panel_button = ttk.Button(
            settings_actions,
            text="ASR >",
            width=9,
            command=self.toggle_asr_panel,
            style="Overlay.TButton",
        )
        self.asr_panel_button.grid(row=2, column=0, sticky="ew")

        asr_summary_label = ttk.Label(
            settings_actions,
            textvariable=self.asr_summary_var,
            anchor="e",
            justify="right",
            style="SettingsDetail.TLabel",
        )
        asr_summary_label.grid(row=3, column=0, sticky="e", pady=(4, 0))

        target_label = ttk.Label(
            self.container,
            textvariable=self.target_var,
            anchor="w",
            justify="left",
            wraplength=520,
            style="Root.TLabel",
        )
        target_label.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        top_button_row = ttk.Frame(self.container, style="Root.TFrame")
        top_button_row.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        for column_index in range(2):
            top_button_row.columnconfigure(column_index, weight=1)

        self.start_button = ttk.Button(
            top_button_row,
            text="Start Recording",
            command=self.on_start_recording,
            style="Overlay.TButton",
        )
        self.start_button.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.stop_button = ttk.Button(
            top_button_row,
            text="Stop & Transcribe",
            command=self.on_stop_transcribe,
            style="Overlay.TButton",
        )
        self.stop_button.grid(row=0, column=1, sticky="ew")

        bottom_button_row = ttk.Frame(self.container, style="Root.TFrame")
        bottom_button_row.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        for column_index in range(3):
            bottom_button_row.columnconfigure(column_index, weight=1)

        self.clear_button = ttk.Button(
            bottom_button_row,
            text="Clear",
            command=self.on_clear,
            style="Overlay.TButton",
        )
        self.clear_button.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.copy_button = ttk.Button(
            bottom_button_row,
            text="Copy Transcript",
            command=self.on_copy,
            style="Overlay.TButton",
        )
        self.copy_button.grid(row=0, column=1, padx=(0, 6), sticky="ew")

        self.paste_button = ttk.Button(
            bottom_button_row,
            text="Paste Last Transcript",
            command=self.on_paste,
            style="Overlay.TButton",
        )
        self.paste_button.grid(row=0, column=2, sticky="ew")

        transcript_label = ttk.Label(
            self.container,
            text="Transcript",
            style="Root.TLabel",
        )
        transcript_label.grid(row=5, column=0, sticky="w", pady=(0, 6))

        self.transcript_box = scrolledtext.ScrolledText(
            self.container,
            wrap="word",
            font=("Segoe UI", 10),
            height=12,
            relief="solid",
            borderwidth=1,
            highlightthickness=1,
        )
        self.transcript_box.grid(row=6, column=0, sticky="nsew")

    def append_transcript(self, text: str) -> None:
        existing = self.get_transcript().strip()
        self.transcript_box.delete("1.0", tk.END)
        if existing and text:
            self.transcript_box.insert("1.0", f"{existing}\n\n{text}")
        else:
            self.transcript_box.insert("1.0", text)

    def clear_transcript(self) -> None:
        self.transcript_box.delete("1.0", tk.END)

    def get_transcript(self) -> str:
        return self.transcript_box.get("1.0", tk.END).strip()

    def set_status(self, status_text: str) -> None:
        self.status_var.set(f"Status: {status_text}")

    def set_hotkey_display(self, status_text: str) -> None:
        self.hotkey_var.set(f"Hotkey: {status_text}")

    def set_target_status(self, status_text: str) -> None:
        self.target_var.set(f"Target: {status_text}")

    def set_show_advanced_devices(self, enabled: bool) -> None:
        self.show_advanced_devices_var.set(bool(enabled))

    def set_asr_preset_display(self, preset: str) -> None:
        normalized_preset = preset.strip().lower() or "balanced"
        self.asr_preset_var.set(normalized_preset)
        self.asr_summary_var.set(normalized_preset.title())

    def set_opacity_display(self, opacity: float) -> None:
        percent = max(35, min(100, int(round(float(opacity) * 100))))
        self.opacity_percent_var.set(percent)
        self.opacity_summary_var.set(f"Opacity: {percent}%")
        self._update_view_summary()

    def set_window_opacity(self, opacity: float) -> None:
        self.root.attributes("-alpha", opacity)
        if self._side_panel is not None and self._side_panel.winfo_exists():
            self._side_panel.attributes("-alpha", opacity)

    def set_dark_mode_enabled(self, enabled: bool) -> None:
        self._dark_mode_enabled = bool(enabled)
        self.dark_mode_var.set(self._dark_mode_enabled)
        self._update_view_summary()
        self._apply_theme()

    def set_microphone_options(
        self,
        option_labels: list[str],
        selected_label: str | None,
    ) -> None:
        self.microphone_combo["values"] = option_labels
        if selected_label is not None:
            self.microphone_var.set(selected_label)
        elif option_labels:
            self.microphone_var.set(option_labels[0])
        else:
            self.microphone_var.set("")

    def set_controls(
        self,
        *,
        can_start: bool,
        can_stop: bool,
        can_clear: bool,
        can_copy: bool,
        can_paste: bool,
        can_change_hotkey: bool,
        can_change_microphone: bool,
        can_refresh_microphones: bool,
        can_toggle_advanced_devices: bool,
    ) -> None:
        self.start_button.config(state=tk.NORMAL if can_start else tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL if can_stop else tk.DISABLED)
        self.clear_button.config(state=tk.NORMAL if can_clear else tk.DISABLED)
        self.copy_button.config(state=tk.NORMAL if can_copy else tk.DISABLED)
        self.paste_button.config(state=tk.NORMAL if can_paste else tk.DISABLED)
        self.change_hotkey_button.config(
            state=tk.NORMAL if can_change_hotkey else tk.DISABLED
        )
        self.microphone_combo.config(
            state="readonly" if can_change_microphone else tk.DISABLED
        )
        self.refresh_microphones_button.config(
            state=tk.NORMAL if can_refresh_microphones else tk.DISABLED
        )
        self.show_advanced_devices_checkbutton.config(
            state=tk.NORMAL if can_toggle_advanced_devices else tk.DISABLED
        )

    def _handle_microphone_selected(self, _event) -> None:
        self.on_microphone_selected(self.microphone_var.get())

    def _handle_show_advanced_devices_toggle(self) -> None:
        self.on_toggle_advanced_devices(bool(self.show_advanced_devices_var.get()))

    def _handle_asr_preset_selected(self) -> None:
        self.on_asr_preset_selected(self.asr_preset_var.get())

    def _handle_opacity_slider(self, value: str) -> None:
        try:
            percent = float(value)
        except (TypeError, ValueError):
            return
        self.on_opacity_changed(percent / 100.0)

    def _apply_quick_opacity(self, percent: int) -> None:
        self.opacity_percent_var.set(percent)
        self.on_opacity_changed(percent / 100.0)

    def _handle_dark_mode_toggle(self) -> None:
        self.on_dark_mode_toggled(bool(self.dark_mode_var.get()))

    def toggle_asr_panel(self) -> None:
        if self._side_panel_kind == "asr":
            self.close_side_panel()
            return

        self.close_side_panel()
        panel = self._create_side_panel("ASR Preset", kind="asr")
        container = ttk.Frame(panel, padding=12, style="Panel.TFrame")
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)

        title_label = ttk.Label(
            container,
            text="ASR Preset",
            font=("Segoe UI", 10, "bold"),
            style="Panel.TLabel",
        )
        title_label.grid(row=0, column=0, sticky="w")

        preset_definitions = [
            (
                "fast",
                "Fast",
                "Rapid, low latency, more mistakes when speaking fast.",
            ),
            (
                "balanced",
                "Balanced",
                "Slightly slower, better Romanian accuracy.",
            ),
            (
                "accurate",
                "Accurate",
                "Slower, more stable for longer or unclear phrases.",
            ),
        ]

        for row_index, (preset_key, preset_title, description) in enumerate(
            preset_definitions,
            start=1,
        ):
            option_frame = ttk.Frame(container, padding=(0, 6, 0, 0), style="Panel.TFrame")
            option_frame.grid(row=row_index, column=0, sticky="ew")
            option_frame.columnconfigure(0, weight=1)

            radio = ttk.Radiobutton(
                option_frame,
                text=preset_title,
                value=preset_key,
                variable=self.asr_preset_var,
                command=self._handle_asr_preset_selected,
                style="Panel.TRadiobutton",
            )
            radio.grid(row=0, column=0, sticky="w")

            description_label = ttk.Label(
                option_frame,
                text=description,
                justify="left",
                wraplength=220,
                style="PanelDetail.TLabel",
            )
            description_label.grid(row=1, column=0, sticky="w", padx=(22, 0))

        self._position_side_panel(panel)

    def toggle_view_panel(self) -> None:
        if self._side_panel_kind == "view":
            self.close_side_panel()
            return

        self.close_side_panel()
        panel = self._create_side_panel("Overlay Visibility", kind="view")
        container = ttk.Frame(panel, padding=12, style="Panel.TFrame")
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)

        title_label = ttk.Label(
            container,
            text="Overlay Visibility",
            font=("Segoe UI", 10, "bold"),
            style="Panel.TLabel",
        )
        title_label.grid(row=0, column=0, sticky="w")

        current_label = ttk.Label(
            container,
            textvariable=self.opacity_summary_var,
            style="Panel.TLabel",
        )
        current_label.grid(row=1, column=0, sticky="w", pady=(8, 4))

        opacity_scale = ttk.Scale(
            container,
            from_=35,
            to=100,
            variable=self.opacity_percent_var,
            orient="horizontal",
            command=self._handle_opacity_slider,
            style="Overlay.Horizontal.TScale",
        )
        opacity_scale.grid(row=2, column=0, sticky="ew")

        quick_buttons = ttk.Frame(container, style="Panel.TFrame")
        quick_buttons.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        for column_index in range(4):
            quick_buttons.columnconfigure(column_index, weight=1)

        for column_index, percent in enumerate((100, 85, 70, 50)):
            button = ttk.Button(
                quick_buttons,
                text=f"{percent}%",
                command=lambda selected_percent=percent: self._apply_quick_opacity(
                    selected_percent
                ),
                style="Overlay.TButton",
            )
            button.grid(
                row=0,
                column=column_index,
                sticky="ew",
                padx=(0, 6) if column_index < 3 else 0,
            )

        dark_mode_checkbutton = ttk.Checkbutton(
            container,
            text="Dark mode",
            variable=self.dark_mode_var,
            command=self._handle_dark_mode_toggle,
            style="Panel.TCheckbutton",
        )
        dark_mode_checkbutton.grid(row=4, column=0, sticky="w", pady=(12, 0))

        self._position_side_panel(panel)

    def close_side_panel(self) -> None:
        if self._side_panel is None:
            self._side_panel_kind = None
            return

        panel = self._side_panel
        self._side_panel = None
        self._side_panel_kind = None
        if panel.winfo_exists():
            panel.destroy()

    def _create_side_panel(self, title: str, *, kind: str) -> tk.Toplevel:
        panel = tk.Toplevel(self.root)
        panel.title(title)
        panel.transient(self.root)
        panel.resizable(False, False)
        panel.attributes("-topmost", self.settings.always_on_top)
        panel.attributes(
            "-alpha",
            max(0.35, min(1.0, self.opacity_percent_var.get() / 100.0)),
        )
        panel.protocol("WM_DELETE_WINDOW", self.close_side_panel)
        panel.bind("<Destroy>", self._handle_side_panel_destroy, add="+")
        self._side_panel = panel
        self._side_panel_kind = kind
        self._apply_theme_to_window(panel)
        return panel

    def _position_side_panel(self, panel: tk.Toplevel) -> None:
        self.root.update_idletasks()
        panel.update_idletasks()
        x_position = self.root.winfo_x() + self.root.winfo_width() + 8
        y_position = self.root.winfo_y()
        panel.geometry(f"+{x_position}+{y_position}")

    def _handle_side_panel_destroy(self, event) -> None:
        if self._side_panel is None:
            return
        if event.widget is self._side_panel:
            self._side_panel = None
            self._side_panel_kind = None

    def _update_view_summary(self) -> None:
        mode_label = "Dark" if self._dark_mode_enabled else "Light"
        opacity_label = f"{int(round(self.opacity_percent_var.get()))}%"
        self.view_summary_var.set(f"{mode_label} | {opacity_label}")

    def _current_palette(self) -> dict[str, str]:
        return DARK_PALETTE if self._dark_mode_enabled else LIGHT_PALETTE

    def _apply_theme(self) -> None:
        palette = self._current_palette()
        self.root.configure(bg=palette["root_bg"])
        self._apply_theme_to_window(self.root)
        if self._side_panel is not None and self._side_panel.winfo_exists():
            self._apply_theme_to_window(self._side_panel)

        self.root.option_add("*TCombobox*Listbox*Background", palette["input_bg"])
        self.root.option_add("*TCombobox*Listbox*Foreground", palette["input_fg"])
        self.root.option_add("*TCombobox*Listbox*selectBackground", palette["selection_bg"])
        self.root.option_add("*TCombobox*Listbox*selectForeground", palette["input_fg"])

        self.style.configure("Root.TFrame", background=palette["root_bg"])
        self.style.configure(
            "Root.TLabel",
            background=palette["root_bg"],
            foreground=palette["fg"],
        )
        self.style.configure(
            "Settings.TLabelframe",
            background=palette["root_bg"],
            bordercolor=palette["border"],
            relief="solid",
        )
        self.style.configure(
            "Settings.TLabelframe.Label",
            background=palette["root_bg"],
            foreground=palette["fg"],
        )
        self.style.configure("SettingsBody.TFrame", background=palette["frame_bg"])
        self.style.configure(
            "SettingsBody.TLabel",
            background=palette["frame_bg"],
            foreground=palette["fg"],
        )
        self.style.configure(
            "SettingsDetail.TLabel",
            background=palette["frame_bg"],
            foreground=palette["muted_fg"],
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "SettingsBody.TCheckbutton",
            background=palette["frame_bg"],
            foreground=palette["fg"],
        )
        self.style.map(
            "SettingsBody.TCheckbutton",
            background=[("active", palette["frame_bg"])],
            foreground=[("disabled", palette["disabled_fg"])],
        )
        self.style.configure("Panel.TFrame", background=palette["frame_bg"])
        self.style.configure(
            "Panel.TLabel",
            background=palette["frame_bg"],
            foreground=palette["fg"],
        )
        self.style.configure(
            "PanelDetail.TLabel",
            background=palette["frame_bg"],
            foreground=palette["muted_fg"],
        )
        self.style.configure(
            "Panel.TCheckbutton",
            background=palette["frame_bg"],
            foreground=palette["fg"],
        )
        self.style.map(
            "Panel.TCheckbutton",
            background=[("active", palette["frame_bg"])],
            foreground=[("disabled", palette["disabled_fg"])],
        )
        self.style.configure(
            "Panel.TRadiobutton",
            background=palette["frame_bg"],
            foreground=palette["fg"],
        )
        self.style.map(
            "Panel.TRadiobutton",
            background=[("active", palette["frame_bg"])],
            foreground=[("disabled", palette["disabled_fg"])],
        )
        self.style.configure(
            "Overlay.TButton",
            background=palette["button_bg"],
            foreground=palette["fg"],
            bordercolor=palette["border"],
        )
        self.style.map(
            "Overlay.TButton",
            background=[
                ("active", palette["button_active_bg"]),
                ("pressed", palette["button_active_bg"]),
                ("disabled", palette["button_bg"]),
            ],
            foreground=[("disabled", palette["disabled_fg"])],
        )
        self.style.configure(
            "Overlay.TCombobox",
            fieldbackground=palette["input_bg"],
            background=palette["button_bg"],
            foreground=palette["input_fg"],
            bordercolor=palette["border"],
            arrowcolor=palette["fg"],
        )
        self.style.map(
            "Overlay.TCombobox",
            fieldbackground=[("readonly", palette["input_bg"])],
            foreground=[
                ("readonly", palette["input_fg"]),
                ("disabled", palette["disabled_fg"]),
            ],
            selectbackground=[("readonly", palette["input_bg"])],
            selectforeground=[("readonly", palette["input_fg"])],
        )
        self.style.configure(
            "Overlay.Horizontal.TScale",
            background=palette["frame_bg"],
        )

        self.transcript_box.configure(
            background=palette["input_bg"],
            foreground=palette["input_fg"],
            insertbackground=palette["input_fg"],
            selectbackground=palette["selection_bg"],
            selectforeground=palette["input_fg"],
            highlightbackground=palette["border"],
            highlightcolor=palette["border"],
        )

    def _apply_theme_to_window(self, window: tk.Misc) -> None:
        palette = self._current_palette()
        try:
            window.configure(bg=palette["root_bg"])
        except tk.TclError:
            return
