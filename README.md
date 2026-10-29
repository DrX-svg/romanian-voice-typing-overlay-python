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

## Optional native DSP and Torch operators

`native/` contains a C++17 static library with no Python or PyTorch dependency.
It provides float/double frame RMS (`sqrt(mean(x*x) + 1e-12)`), peak normalization,
and offline trim bounds. `src/voice_typing_ro/dsp.py` provides vectorized NumPy
reference implementations and selects `torch_cpp` when the optional extension
imports, otherwise `numpy`.

Recording preprocessing is disabled by default. To enable it, set the JSON boolean
`audio.preprocess` to `true` in `config.json`. It processes only mono int16 audio
after recording stops: 25 ms frames, 10 ms hops, -45 dBFS trimming with 200 ms
padding, then peak normalization to 0.9. Trims shorter than 0.25 seconds retain the
untrimmed recording. WAV frame counts and duration reflect the processed audio.
Stereo input is returned unchanged with a warning. Use real JSON booleans, since
string boolean normalization remains an open issue in `docs/DEFECTS.md`.
This does not add VAD or automatic stopping.

### Windows build and tests

Run from the repository root using Python 3.10 or later and MSVC Build Tools 2022.
The tested CPU PyTorch release is 2.8.0 (installed as `2.8.0+cpu`), released
[August 6, 2025](https://pytorch.org/blog/pytorch-2-8/).

```powershell
python -m venv .venv # Only if the environment does not already exist.
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt cmake ninja setuptools wheel
.venv/Scripts/python.exe -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu

# Enter the MSVC environment before every native build, then return to the repo.
$repoPath = (Get-Location).Path
& "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\Launch-VsDevShell.ps1" -Arch amd64 -HostArch amd64
Set-Location -LiteralPath $repoPath
$env:PATH = "$repoPath\.venv\Scripts;$env:PATH"
$env:DISTUTILS_USE_SDK = '1'
$env:MAX_JOBS = '2'

cmake -S native -B native/build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build native/build
ctest --test-dir native/build --output-on-failure
.venv/Scripts/python.exe native/torch_ext/setup.py build_ext --inplace
.venv/Scripts/python.exe -m pytest -v
.venv/Scripts/python.exe benchmarks/bench_dsp.py
```

GoogleTest is downloaded via FetchContent, pinned to `v1.14.0`. No Whisper model
is required. Building only the static library and CTest tests does not require
PyTorch. The Torch extension compiles the same `native/src/dsp.cpp` core and
creates an ignored `.pyd` in the repo root; rebuild it when Python/PyTorch changes.

### Linux build and tests

Install a C++17 compiler and Git, then run from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt cmake ninja setuptools wheel
python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
cmake -S native -B native/build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build native/build
ctest --test-dir native/build --output-on-failure
MAX_JOBS=2 python native/torch_ext/setup.py build_ext --inplace
python -m pytest -v
python benchmarks/bench_dsp.py
```

The extension exposes `vt_dsp_torch.frame_rms`, `normalize_peak`, and `trim_bounds`.
All accept CPU float32/float64 1-D tensors and make noncontiguous inputs contiguous.
`frame_rms` uses a `torch.autograd.Function` with its forward and first-order
backward numeric routines in C++; overlapping frame gradients accumulate.
Higher-order derivatives are explicitly unsupported. The other two operations are
forward-only. Python tests skip the extension module when Torch or the extension
is absent; the CI extension job checks imports explicitly so these tests run.
Normal test jobs require only `requirements-dev.txt` and use the NumPy fallback.

### Local verification and benchmark

Verified on Windows with Python 3.11.9, NumPy 2.4.6, CPU Torch 2.8.0+cpu,
CMake 4.4.4, Ninja 1.13.2, MSVC compiler 19.44.35229.0 (toolset 14.44.35207),
and GoogleTest 1.14.0: 8/8 CTest tests passed; pytest reported 116 passed,
1 existing strict xfail, 0 skipped, 0 failed. Linux and GitHub Actions execution
were not verified locally. No GUI, microphone, Whisper model or GPU was used.

Benchmark output on a 12th Gen Intel(R) Core(TM) i7-12650H, 30 seconds at 16 kHz,
float32, five warm-ups and the median of 50 runs:

| Operation | NumPy ms | C++ ms | NumPy/C++ |
| --- | ---: | ---: | ---: |
| frame_rms | 2.512500000 | 0.563050000 | 4.462303525 |
| trim_bounds | 2.541050000 | 0.510050000 | 4.981962553 |
| normalize_peak | 1.242500000 | 1.272850000 | 0.976155871 |
| pipeline | 6.029950000 | 2.372750000 | 2.541333895 |

Tensor views are prepared before timing; dispatch and output allocation are
included. The pipeline measures RMS, trim bounds and normalization of the trimmed
signal for both implementations. These are local measurements, not a universal
speed guarantee; peak normalization alone was slightly slower in C++.

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
