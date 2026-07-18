import json

from sqlalchemy import text

from powermouse.adapters.profile import SqlAlchemyProfileManager
from powermouse.adapters.voice import (
    SoundDeviceMicrophoneCapture,
    SoundDeviceMicrophoneManager,
    VoskSpeechRecognizer,
)
from powermouse.domain.controllers.voice import MicrophoneManager
from powermouse.domain.models.gesture import GestureEvent
from powermouse.domain.models.mouse import ClickInterface, MouseButton, MouseEventType
from powermouse.domain.models.microphone import Microphone
from powermouse.domain.usecases.gesture_mapping import GestureToMouseTranslator
from powermouse.domain.usecases.mouse_actions import MouseActionCoordinator
from powermouse.domain.usecases.voice_clicking import (
    CLICK_PHRASES,
    HOLD_PHRASES,
    RELEASE_PHRASES,
    VOICE_PHRASES,
    VoiceToMouseTranslator,
    voice_clicking_step,
)


def kinds(events):
    return [(event.button, event.event_type) for event in events]


def test_voice_click_and_unknown():
    translator = VoiceToMouseTranslator()
    assert kinds(translator.translate("right click", (1, 2))) == [
        (MouseButton.RIGHT, MouseEventType.BUTTON_DOWN),
        (MouseButton.RIGHT, MouseEventType.BUTTON_UP),
    ]
    assert translator.translate("[unk]", (0, 0)) == []


def test_duplicate_hold_release_and_click_while_held():
    translator = VoiceToMouseTranslator()
    assert len(translator.translate("hold click", (0, 0))) == 1
    assert translator.translate("hold click", (0, 0)) == []
    assert translator.translate("click", (0, 0)) == []
    assert len(translator.translate("release click", (0, 0))) == 1
    assert translator.translate("release click", (0, 0)) == []


def test_other_buttons_can_be_clicked_during_drag():
    translator = VoiceToMouseTranslator()
    translator.translate("start drag", (0, 0))

    assert kinds(translator.translate("right click", (1, 2))) == [
        (MouseButton.RIGHT, MouseEventType.BUTTON_DOWN),
        (MouseButton.RIGHT, MouseEventType.BUTTON_UP),
    ]


def test_every_supported_phrase_maps_to_its_declared_action():
    for phrase, (button, count) in CLICK_PHRASES.items():
        assert kinds(VoiceToMouseTranslator().translate(phrase, (0, 0))) == [
            (button, event_type)
            for _ in range(count)
            for event_type in (
                MouseEventType.BUTTON_DOWN,
                MouseEventType.BUTTON_UP,
            )
        ]

    for phrase, button in HOLD_PHRASES.items():
        assert kinds(VoiceToMouseTranslator().translate(phrase, (0, 0))) == [
            (button, MouseEventType.BUTTON_DOWN)
        ]

    for phrase, button in RELEASE_PHRASES.items():
        coordinator = MouseActionCoordinator()
        coordinator.acquire(ClickInterface.VOICE, button, (0, 0))
        assert kinds(VoiceToMouseTranslator(coordinator).translate(phrase, (0, 0))) == [
            (button, MouseEventType.BUTTON_UP)
        ]


def test_shared_gesture_voice_ownership():
    coordinator = MouseActionCoordinator()
    gesture = GestureToMouseTranslator(coordinator)
    voice = VoiceToMouseTranslator(coordinator)
    assert len(gesture.translate(GestureEvent.OPEN_MOUTH, (0, 0))) == 1
    assert voice.translate("hold click", (0, 0)) == []
    assert gesture.reset_holds((0, 0)) == []
    assert kinds(voice.reset_holds((0, 0))) == [(MouseButton.LEFT, MouseEventType.BUTTON_UP)]


class FakeRecognizer:
    def __init__(self):
        self.phrases = ["click", "right click"]

    def detect_phrase(self):
        return self.phrases.pop(0) if self.phrases else None


class FakeMouse:
    def __init__(self):
        self.events = []

    def handle_event(self, event):
        self.events.append(event)


def test_disabled_step_drains_without_dispatch():
    recognizer, mouse = FakeRecognizer(), FakeMouse()
    voice_clicking_step(recognizer, VoiceToMouseTranslator(), mouse, (0, 0), False)
    assert recognizer.phrases == []
    assert mouse.events == []


class FakeSoundDevice:
    class Default:
        device = [1, 0]

    default = Default()
    devices = [
        {"name": "Speakers", "max_input_channels": 0},
        {
            "name": "Built-in Microphone",
            "max_input_channels": 1,
            "default_samplerate": 48_000,
        },
        {
            "name": "USB Microphone",
            "max_input_channels": 2,
            "default_samplerate": 44_100,
        },
    ]

    @classmethod
    def query_devices(cls, index=None):
        return cls.devices if index is None else cls.devices[index]


def test_microphone_manager_enumerates_default_and_rebinds_unique_name():
    manager = SoundDeviceMicrophoneManager(FakeSoundDevice)

    assert manager.get_microphones() == [
        Microphone("1", "Built-in Microphone"),
        Microphone("2", "USB Microphone"),
    ]
    assert manager.get_default_microphone() == Microphone(
        "1", "Built-in Microphone"
    )
    assert manager.resolve_microphone(Microphone("9", "USB Microphone")) == (
        Microphone("2", "USB Microphone")
    )
    assert manager.resolve_microphone(Microphone("2", "Different Device")) is None


def test_duplicate_microphone_names_cannot_be_ambiguously_rebound():
    class DuplicateNameManager(MicrophoneManager):
        def get_microphones(self):
            return [Microphone("1", "USB"), Microphone("2", "USB")]

    assert (
        DuplicateNameManager().resolve_microphone(Microphone("9", "USB")) is None
    )


def test_audio_callback_drops_overflow_without_blocking():
    capture = SoundDeviceMicrophoneCapture(FakeSoundDevice, queue_size=1)

    capture._callback(b"first", 0, None, None)
    capture._callback(b"dropped", 0, None, None)

    assert capture.read(timeout=0) == b"first"
    assert capture.read(timeout=0) is None


class FakeKaldiRecognizer:
    def __init__(self, model, sample_rate, grammar):
        self.model = model
        self.sample_rate = sample_rate
        self.grammar = grammar
        self.accept_final = False
        self.reset_calls = 0

    def AcceptWaveform(self, pcm):
        return self.accept_final

    def Result(self):
        return json.dumps({"text": "start right drag"})

    def Reset(self):
        self.reset_calls += 1


def test_vosk_uses_constrained_grammar_and_only_emits_final_results():
    created = []

    def recognizer_factory(*args):
        recognizer = FakeKaldiRecognizer(*args)
        created.append(recognizer)
        return recognizer

    recognizer = VoskSpeechRecognizer(
        model_factory=lambda path: path,
        recognizer_factory=recognizer_factory,
    )
    recognizer.start(16_000)
    kaldi = created[0]

    assert json.loads(kaldi.grammar) == [*VOICE_PHRASES, "[unk]"]
    recognizer.process_audio(b"partial")
    assert recognizer.detect_phrase() is None

    kaldi.accept_final = True
    recognizer.process_audio(b"final")
    assert recognizer.detect_phrase() == "start right drag"


def test_profile_persists_microphone_identity(populated_profile_manager):
    profile = populated_profile_manager.get_active_profile()
    profile.microphone = Microphone("4", "Desk Microphone")
    populated_profile_manager.update_profile(profile.profile_id, profile)

    assert populated_profile_manager.get_active_profile().microphone == Microphone(
        "4", "Desk Microphone"
    )


def test_legacy_profile_database_adds_nullable_microphone_columns(
    tmp_path, sample_profile
):
    database = tmp_path / "profiles.db"
    db_url = f"sqlite:///{database}"
    manager = SqlAlchemyProfileManager(db_url=db_url)
    manager.create_profile(sample_profile)
    with manager._engine.begin() as connection:
        connection.execute(text("ALTER TABLE profiles DROP COLUMN microphone_id"))
        connection.execute(text("ALTER TABLE profiles DROP COLUMN microphone_name"))

    upgraded = SqlAlchemyProfileManager(db_url=db_url)

    assert upgraded.get_active_profile().microphone is None
    with upgraded._engine.begin() as connection:
        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(profiles)"))
        }
        assert {"microphone_id", "microphone_name"} <= columns


def test_profile_migration_does_not_downgrade_future_schema_version(tmp_path):
    database = tmp_path / "profiles.db"
    db_url = f"sqlite:///{database}"
    manager = SqlAlchemyProfileManager(db_url=db_url)
    with manager._engine.begin() as connection:
        connection.execute(text("PRAGMA user_version = 7"))

    reopened = SqlAlchemyProfileManager(db_url=db_url)
    with reopened._engine.begin() as connection:
        assert connection.execute(text("PRAGMA user_version")).scalar_one() == 7
