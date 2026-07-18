from __future__ import annotations

import json
import queue
import threading
from importlib.resources import files
from typing import Any

import sounddevice
import vosk

from powermouse.domain.controllers.voice import (
    MicrophoneCapture,
    MicrophoneManager,
    SpeechRecognizer,
)
from powermouse.domain.models.microphone import Microphone
from powermouse.domain.usecases.voice_clicking import VOICE_PHRASES


class SoundDeviceMicrophoneManager(MicrophoneManager):
    def __init__(self, sounddevice_module=sounddevice):
        self._sd = sounddevice_module

    def get_microphones(self) -> list[Microphone]:
        result: list[Microphone] = []
        for index, device in enumerate(self._sd.query_devices()):
            if int(device.get("max_input_channels", 0)) <= 0:
                continue
            result.append(
                Microphone(str(index), str(device.get("name", "Microphone")))
            )
        return result

    def get_default_microphone(self) -> Microphone | None:
        devices = self.get_microphones()
        configured = self._sd.default.device
        try:
            configured = configured[0]
        except (KeyError, TypeError):
            pass
        if configured is None or int(configured) < 0:
            return None
        return next(
            (microphone for microphone in devices if microphone.id == str(configured)),
            None,
        )


class SoundDeviceMicrophoneCapture(MicrophoneCapture):
    def __init__(self, sounddevice_module=sounddevice, queue_size: int = 32):
        self._sd = sounddevice_module
        self._pcm: queue.Queue[bytes] = queue.Queue(maxsize=queue_size)
        self._errors: queue.Queue[str] = queue.Queue(maxsize=1)
        self._stream = None
        self._sample_rate = 0.0
        self._lock = threading.Lock()
        self._stopping = False

    @property
    def sample_rate(self) -> float:
        return self._sample_rate

    def _callback(self, indata, frames, time_info, status):  # noqa: ARG002
        try:
            self._pcm.put_nowait(bytes(indata))
        except queue.Full:
            # The PortAudio callback must never block. Dropping one chunk is
            # preferable to stalling the real-time audio thread.
            pass

    def _finished_callback(self) -> None:
        if self._stopping:
            return
        try:
            self._errors.put_nowait("Microphone stream stopped unexpectedly.")
        except queue.Full:
            pass

    def start(self, microphone: Microphone) -> None:
        with self._lock:
            if self._stream is not None:
                return
            self._drain(self._pcm)
            self._drain(self._errors)
            self._stopping = False
            device = int(microphone.id)
            info = self._sd.query_devices(device)
            self._sample_rate = float(info["default_samplerate"])
            stream = self._sd.RawInputStream(
                device=device,
                samplerate=self._sample_rate,
                channels=1,
                dtype="int16",
                callback=self._callback,
                finished_callback=self._finished_callback,
            )
            try:
                stream.start()
            except Exception:
                stream.close()
                self._sample_rate = 0.0
                raise
            else:
                self._stream = stream

    def read(self, timeout: float = 0.1) -> bytes | None:
        try:
            return self._pcm.get(timeout=timeout)
        except queue.Empty:
            return None

    def detect_error(self) -> str | None:
        try:
            return self._errors.get_nowait()
        except queue.Empty:
            return None

    def stop(self) -> None:
        with self._lock:
            self._stopping = True
            stream, self._stream = self._stream, None
            if stream is not None:
                stream.stop()
                stream.close()
            self._sample_rate = 0.0
            self._drain(self._pcm)
            self._drain(self._errors)

    @staticmethod
    def _drain(items: queue.Queue[Any]) -> None:
        while True:
            try:
                items.get_nowait()
            except queue.Empty:
                return


class VoskSpeechRecognizer(SpeechRecognizer):
    def __init__(self, model_factory=vosk.Model, recognizer_factory=vosk.KaldiRecognizer):
        self._model_factory = model_factory
        self._recognizer_factory = recognizer_factory
        self._model = None
        self._recognizer = None
        self._phrases: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        vosk.SetLogLevel(-1)

    def start(self, sample_rate: float) -> None:
        self.stop()
        if self._model is None:
            model_path = files("powermouse.resources").joinpath(
                "vosk-model-small-en-us-0.15"
            )
            self._model = self._model_factory(str(model_path))
        grammar = json.dumps([*VOICE_PHRASES, "[unk]"])
        with self._lock:
            self._recognizer = self._recognizer_factory(
                self._model, sample_rate, grammar
            )

    def process_audio(self, pcm: bytes) -> None:
        with self._lock:
            recognizer = self._recognizer
            if recognizer is not None and recognizer.AcceptWaveform(pcm):
                text = json.loads(recognizer.Result()).get("text", "").strip().lower()
                if text and text != "[unk]":
                    self._phrases.put(text)

    def detect_phrase(self) -> str | None:
        try:
            return self._phrases.get_nowait()
        except queue.Empty:
            return None

    def reset(self) -> None:
        with self._lock:
            if self._recognizer is not None and hasattr(self._recognizer, "Reset"):
                self._recognizer.Reset()
        while self.detect_phrase() is not None:
            pass

    def stop(self) -> None:
        with self._lock:
            recognizer = self._recognizer
            self._recognizer = None
            if recognizer is not None and hasattr(recognizer, "Reset"):
                recognizer.Reset()
        while self.detect_phrase() is not None:
            pass


class RecognitionWorker:
    def __init__(self, capture: MicrophoneCapture, recognizer: SpeechRecognizer):
        self.capture, self.recognizer = capture, recognizer
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._errors: queue.Queue[tuple[int, str]] = queue.Queue(maxsize=1)
        self._generation = 0

    @property
    def generation(self) -> int:
        return self._generation

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        while self.detect_error() is not None:
            pass
        # Initialize Vosk before launching the worker so model/open failures
        # are reported to the caller and a microphone switch can be rolled back.
        self.recognizer.start(self.capture.sample_rate)
        self._stop.clear()
        self._generation += 1
        generation = self._generation
        self._thread = threading.Thread(
            target=self._run,
            args=(generation,),
            name="voice-recognition",
            daemon=False,
        )
        self._thread.start()

    def _run(self, generation: int) -> None:
        try:
            while not self._stop.is_set():
                error = self.capture.detect_error()
                if error is not None:
                    raise RuntimeError(error)
                pcm = self.capture.read(0.1)
                if pcm:
                    self.recognizer.process_audio(pcm)
        except Exception as exc:
            if not self._stop.is_set():
                try:
                    self._errors.put_nowait((generation, str(exc)))
                except queue.Full:
                    pass
        finally:
            if not self._stop.is_set():
                self.capture.stop()
                self.recognizer.stop()

    def detect_error(self) -> tuple[int, str] | None:
        try:
            return self._errors.get_nowait()
        except queue.Empty:
            return None

    def stop(self) -> None:
        self._stop.set()
        self.capture.stop()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join()
        self.recognizer.stop()
        self._thread = None
