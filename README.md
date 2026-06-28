# Romanian Voice Typing Overlay

Romanian voice typing overlay for Windows using `faster-whisper` and Whisper Large-v3 Turbo.

Version: `0.8.0`

## Overview

Romanian Voice Typing Overlay is a local desktop application for Romanian dictation on Windows. It provides a lightweight always-on-top overlay with microphone selection, configurable transcription presets, and quick paste or copy workflows for text entry.

## Features

- Local Romanian speech-to-text
- `faster-whisper` transcription
- Configurable global hotkey
- Paste into the active window
- Microphone selection with simplified and advanced device lists
- ASR presets: `Fast`, `Balanced`, `Accurate`
- Dark mode
- Adjustable window opacity
- Always-on-top overlay

## Requirements

- Windows
- Python `3.10` recommended
- A working microphone
- Optional NVIDIA GPU/CUDA for faster transcription

## Installation

Clone the repository, open PowerShell in the project folder, and choose one of the following setup paths.

The default configuration uses CPU transcription (`device = cpu`, `compute_type = int8`) for broad compatibility. CUDA is optional and can be enabled later on compatible NVIDIA systems.

Internet access is required for the first setup and for the first model download. 

`setup_windows.ps1` installs the Python dependencies. The first time you start the overlay with `run_overlay.ps1`, the configured Whisper model may be downloaded from Hugging Face.

After the model is available locally, transcription runs locally and does not use an online speech-to-text API

### Option 1: Quick Windows setup

```powershell
.\setup_windows.ps1
```

### Option 2: Manual virtual environment setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Usage

Start the overlay:

```powershell
.\run_overlay.ps1
```

On first launch, the app creates `config.json` automatically if it does not already exist.

Typical workflow:

1. Launch the overlay.
2. Choose a microphone if needed.
3. Choose an ASR preset if needed.
4. Press `F10` to start recording.
5. Speak a short Romanian phrase.
6. Press `F10` again to stop and transcribe.
7. Review the transcript and paste or copy it.

The hotkey can be changed from the GUI and is saved to `config.json`.

## Configuration

- `config.json` is created automatically on first run.
- `config.example.json` is included as a reference.
- If `config.json` is missing, the app recreates it from default settings.
- If `config.json` is invalid JSON, the app keeps a backup and regenerates defaults.

Default transcription settings:

- `language`: `ro`
- `asr_preset`: `balanced`
- `beam_size`: `3`
- `device`: `cpu`
- `compute_type`: `int8`
- `download_root`: `%LOCALAPPDATA%\RomanianVoiceTyping\models`

To use CUDA on a compatible NVIDIA system, update `config.json` after first run:

```json
"device": "cuda",
"compute_type": "int8_float16"
```

## ASR Presets

- `Fast` = `beam_size 1`
- `Balanced` = `beam_size 3`
- `Accurate` = `beam_size 5`

`Balanced` is the recommended default for Romanian dictation.

## Microphone Selection

- The GUI exposes a microphone dropdown and a `Refresh Microphones` button.
- Simplified mode keeps the list focused on likely real microphones and headsets.
- `Show advanced devices` exposes the full input-capable device list when needed.
- Saved microphone choices are restored when possible and fall back safely if the device disappears.

## Overlay Options

- `View >` opens window appearance controls.
- Opacity can be adjusted from `35%` to `100%`.
- `Dark mode` can be toggled on or off.
- These settings are persisted in `config.json`.

## Local Model Download

- The repository does not include Whisper model files.
- The first run may download the configured model.
- By default, model files are stored under `%LOCALAPPDATA%\RomanianVoiceTyping\models`.

## Limitations

- Windows-focused desktop application
- Auto-paste is best-effort and depends on target app focus and permissions
- Local transcription quality depends on microphone quality, room noise, and speech clarity
- This is a source-based Python release, not a packaged installer

## Roadmap

- Packaged Windows installer
- System tray mode
- Voice punctuation commands
- Improved onboarding

## Project Summary

Romanian Voice Typing Overlay combines local speech-to-text, microphone device handling, a Tkinter overlay, global hotkeys, and clipboard or paste automation into a focused Romanian dictation workflow for Windows.

## License

This project is licensed under the GNU General Public License v3.0.

Copyright (c) 2026 DrX-svg.

This repository’s original source code is licensed under the GNU General Public License v3.0. Third-party libraries and model files remain under their respective licenses.
