"""VoicePool — hands out a distinct Kokoro voice (and a spoken name) to each
dynamically spawned sub-agent, and takes it back when the agent retires.

Ranked by Kokoro's own published quality grades (hexgrad/Kokoro-82M
VOICES.md), not alphabetically: only ~12 of the 28 English voices grade C+
or better, and the American male voices are noticeably weaker than the
female ones. Female and male entries are interleaved so two sub-agents
spawned back to back never sound alike. af_heart (HOPE) and af_bella
(Atlas) are the two best voices and are reserved, not pooled.

The spoken name is how Pavan addresses a sub-agent by voice ("let me talk
to Emma") — it has to survive STT, so it's a plain common first name, never
"researcher-3".
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PooledVoice:
    voice_id: str
    spoken_name: str


# Best first, alternating female and male. Every entry is in the stock
# voices-v1.0.bin. af_nicole is left out on purpose: its whispery, breathy
# delivery is wrong for a research assistant, and Pavan asked for it gone.
POOL: tuple[PooledVoice, ...] = (
    PooledVoice("af_sarah", "Sarah"),
    PooledVoice("am_michael", "Michael"),
    PooledVoice("bf_emma", "Emma"),
    PooledVoice("am_fenrir", "Fenrir"),
    PooledVoice("af_kore", "Kore"),
    PooledVoice("am_puck", "Puck"),
    PooledVoice("af_aoede", "Aoede"),
    PooledVoice("bm_george", "George"),
    PooledVoice("bf_isabella", "Isabella"),
    PooledVoice("bm_fable", "Fable"),
    PooledVoice("af_nova", "Nova"),
    PooledVoice("af_alloy", "Alloy"),
)


class VoicePoolExhausted(RuntimeError):
    pass


class VoicePool:
    def __init__(
        self,
        reserved: set[str] | None = None,
        pool: tuple[PooledVoice, ...] = POOL,
    ) -> None:
        self._pool = tuple(v for v in pool if v.voice_id not in (reserved or set()))
        self._leased: dict[str, PooledVoice] = {}  # spoken_name.lower() -> voice

    def lease(self) -> PooledVoice:
        """The best voice nobody is using. Raises VoicePoolExhausted rather
        than reusing a voice — two live agents sharing one voice is exactly
        the confusion this class exists to prevent."""
        for voice in self._pool:
            if voice.spoken_name.lower() not in self._leased:
                self._leased[voice.spoken_name.lower()] = voice
                return voice
        raise VoicePoolExhausted(f"All {len(self._pool)} sub-agent voices are in use.")

    def release(self, spoken_name: str) -> None:
        self._leased.pop(spoken_name.lower(), None)

    def in_use(self) -> list[PooledVoice]:
        return list(self._leased.values())

    def available(self) -> int:
        return len(self._pool) - len(self._leased)
