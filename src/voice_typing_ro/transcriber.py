# Romanian Voice Typing Overlay
# Copyright (C) 2026 DrX-svg
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from .model_bootstrap import bootstrap_cuda_dll_paths
from .settings import AppSettings


class TranscriberError(RuntimeError):
    pass


class LocalWhisperTranscriber:
    def __init__(self, settings: AppSettings, logger: logging.Logger):
        self.settings = settings
        self.logger = logger
        self._model = None
        self._beam_size = settings.beam_size
        self._load_error: Exception | None = None
        self._ready_event = threading.Event()
        self._load_thread: threading.Thread | None = None

    @property
    def is_ready(self) -> bool:
        return self._ready_event.is_set() and self._load_error is None and self._model is not None

    @property
    def load_error(self) -> Exception | None:
        return self._load_error

    @property
    def beam_size(self) -> int:
        return self._beam_size

    def set_beam_size(self, beam_size: int) -> None:
        self._beam_size = int(beam_size)
        self.logger.info("Transcriber beam size updated for future transcriptions: %s", self._beam_size)

    def load_async(self, callback) -> None:
        if self._load_thread and self._load_thread.is_alive():
            return

        def worker() -> None:
            try:
                self._load_model()
            except Exception as exc:  # pragma: no cover - model load is runtime-specific
                self._load_error = exc
                self.logger.exception("Model load failed.")
                callback(False, str(exc))
                return

            callback(True, None)

        self._load_thread = threading.Thread(
            target=worker,
            name="model-loader",
            daemon=True,
        )
        self._load_thread.start()

    def transcribe_file(self, audio_path: Path) -> tuple[str, float]:
        if not self.is_ready:
            raise TranscriberError("Whisper model is not ready.")

        start_time = time.perf_counter()
        self.logger.info(
            "Transcribing audio file: %s beam_size=%s",
            audio_path,
            self._beam_size,
        )

        segments, info = self._model.transcribe(
            str(audio_path),
            language=self.settings.language,
            beam_size=self._beam_size,
            without_timestamps=self.settings.without_timestamps,
            condition_on_previous_text=self.settings.condition_on_previous_text,
            vad_filter=self.settings.vad_filter,
        )

        text_parts = []
        for segment in segments:
            cleaned = (segment.text or "").strip()
            if cleaned:
                text_parts.append(cleaned)

        elapsed = time.perf_counter() - start_time
        text = " ".join(text_parts).strip()
        self.logger.info(
            "Transcription finished in %.2fs. audio_duration=%.2fs text_length=%s",
            elapsed,
            info.duration,
            len(text),
        )
        return text, elapsed

    def _load_model(self) -> None:
        bootstrap_cuda_dll_paths(self.logger)
        from faster_whisper import WhisperModel

        start_time = time.perf_counter()
        self.logger.info(
            "Loading Whisper model. model=%s device=%s compute_type=%s",
            self.settings.model_name,
            self.settings.device,
            self.settings.compute_type,
        )

        self._model = WhisperModel(
            self.settings.model_name,
            device=self.settings.device,
            compute_type=self.settings.compute_type,
            download_root=str(self.settings.download_root),
        )

        elapsed = time.perf_counter() - start_time
        self._ready_event.set()
        self.logger.info("Whisper model loaded in %.2fs.", elapsed)
