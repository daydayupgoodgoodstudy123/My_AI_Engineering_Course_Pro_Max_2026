"""A Pipecat-shaped voice pipeline: VAD -> STT -> LLM -> TTS -> transport.

Each processor handles the frames it knows and forwards the rest: downstream
frames to the next processor, upstream frames to the previous one.

The audio is scripted: an audio_chunk payload is the text the user says in that
chunk, and a chunk that is empty or only whitespace is silence.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .frames import DOWNSTREAM, UPSTREAM, Frame


class Processor:
    def __init__(self, name: str) -> None:
        self.name = name
        self.next: Processor | None = None
        self.prev: Processor | None = None

    def process(self, frame: Frame) -> None:
        """Forward a frame this processor does not handle."""
        if frame.direction == DOWNSTREAM:
            if self.next is not None:
                self.next.process(frame)
        elif self.prev is not None:
            self.prev.process(frame)


class VAD(Processor):
    """Passes speech on as vad_speech frames. Silent chunks stop here."""

    def process(self, frame: Frame) -> None:
        if frame.kind == "audio_chunk":
            if str(frame.payload).strip():
                super().process(Frame("vad_speech", frame.payload))
        else:
            super().process(frame)


class STT(Processor):
    """Turns each vad_speech frame into a transcript frame."""

    def process(self, frame: Frame) -> None:
        if frame.kind == "vad_speech":
            super().process(Frame("transcript", str(frame.payload).strip()))
        else:
            super().process(frame)


class LLM(Processor):
    """Answers each transcript with one text frame.

    context alternates user and assistant messages. model(messages) gets a copy of
    the context that ends with the new user message and returns the reply. Each
    reply carries the next turn number; the first reply is turn 1.

    A cancel coming upstream cuts the last assistant message down to the words the
    user heard, which the cancel frame carries as its payload.
    """

    def __init__(self, model: Callable[[list[dict]], str], name: str = "llm") -> None:
        super().__init__(name)
        self.model = model
        self.context: list[dict] = []
        self.turn = 0

    def process(self, frame: Frame) -> None:
        if frame.kind == "transcript":
            self.context.append({"role": "user", "content": frame.payload})
            reply = self.model([dict(m) for m in self.context])
            self.turn += 1
            self.context.append({"role": "assistant", "content": reply})
            super().process(Frame("text", reply, turn=self.turn))
        elif frame.kind == "cancel":
            if self.context and self.context[-1]["role"] == "assistant":
                self.context[-1]["content"] = " ".join(frame.payload)
            super().process(frame)
        else:
            super().process(frame)


class TTS(Processor):
    """Speaks each text frame word by word.

    synthesize(word) returns the audio for one word. Each word goes downstream as its
    own tts_audio frame as soon as it is synthesized, so the user hears the first
    word without waiting for the rest of the reply.

    A cancel (barge-in) stops the current utterance: no word synthesized after the
    cancel is played. The cancel goes on upstream carrying the words of the latest
    utterance that were handed to the transport.
    """

    def __init__(self, synthesize: Callable[[str], bytes], name: str = "tts") -> None:
        super().__init__(name)
        self.synthesize = synthesize
        self.cancelled = False
        self.spoken: list[str] = []

    def process(self, frame: Frame) -> None:
        if frame.kind == "text":
            self.cancelled = False
            self.spoken = []
            for word in str(frame.payload).split():
                if self.cancelled:
                    break
                chunk = self.synthesize(word)
                if self.cancelled:
                    break
                self.spoken.append(word)
                super().process(Frame("tts_audio", chunk, turn=frame.turn))
        elif frame.kind == "cancel":
            self.cancelled = True
            super().process(Frame("cancel", list(self.spoken), UPSTREAM, frame.turn))
        else:
            super().process(frame)


class Transport(Processor):
    """Sink: plays each tts_audio frame through play(audio).

    The transport calls barge_in() when the user talks over the bot; it sends a
    cancel frame upstream.
    """

    def __init__(self, play: Callable[[bytes], None], name: str = "transport") -> None:
        super().__init__(name)
        self.play = play

    def process(self, frame: Frame) -> None:
        if frame.kind == "tts_audio":
            self.play(frame.payload)
        else:
            super().process(frame)

    def barge_in(self) -> None:
        self.process(Frame("cancel", None, UPSTREAM))


def link(*processors: Processor) -> None:
    for a, b in zip(processors, processors[1:]):
        a.next = b
        b.prev = a


@dataclass
class VoicePipeline:
    vad: VAD
    stt: STT
    llm: LLM
    tts: TTS
    transport: Transport

    def hear(self, text: str) -> None:
        """Feed one scripted audio chunk in at the source."""
        self.vad.process(Frame("audio_chunk", text))


def build_pipeline(
    model: Callable[[list[dict]], str],
    synthesize: Callable[[str], bytes],
    play: Callable[[bytes], None],
) -> VoicePipeline:
    pipe = VoicePipeline(VAD("vad"), STT("stt"), LLM(model), TTS(synthesize), Transport(play))
    link(pipe.vad, pipe.stt, pipe.llm, pipe.tts, pipe.transport)
    return pipe
