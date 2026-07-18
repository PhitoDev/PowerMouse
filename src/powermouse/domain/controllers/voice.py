from powermouse.domain.models.microphone import Microphone


class MicrophoneManager:
    def get_microphones(self) -> list[Microphone]:
        raise NotImplementedError

    def get_default_microphone(self) -> Microphone | None:
        raise NotImplementedError

    def resolve_microphone(self, saved: Microphone) -> Microphone | None:
        """Resolve a persisted device after PortAudio indexes may have changed."""
        microphones = self.get_microphones()
        exact = next(
            (
                microphone
                for microphone in microphones
                if microphone.id == saved.id and microphone.name == saved.name
            ),
            None,
        )
        if exact is not None:
            return exact

        name_matches = [
            microphone for microphone in microphones if microphone.name == saved.name
        ]
        return name_matches[0] if len(name_matches) == 1 else None


class MicrophoneCapture:
    @property
    def sample_rate(self) -> float:
        raise NotImplementedError

    def start(self, microphone: Microphone) -> None:
        raise NotImplementedError

    def read(self, timeout: float = 0.1) -> bytes | None:
        raise NotImplementedError

    def detect_error(self) -> str | None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


class SpeechRecognizer:
    def start(self, sample_rate: float) -> None:
        raise NotImplementedError

    def process_audio(self, pcm: bytes) -> None:
        raise NotImplementedError

    def detect_phrase(self) -> str | None:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError
