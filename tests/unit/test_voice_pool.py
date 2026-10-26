"""Unit tests for core/voice/voice_pool.py — one distinct voice per live sub-agent."""

import pytest

from core.voice.voice_pool import POOL, PooledVoice, VoicePool, VoicePoolExhausted

# The 54 voices in the stock voices-v1.0.bin that the pool may draw from.
_ENGLISH_STOCK_VOICES = {
    "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole",
    "af_nova", "af_river", "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir",
    "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa", "bf_alice", "bf_emma",
    "bf_isabella", "bf_lily", "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
}


@pytest.mark.unit
def test_every_pooled_voice_is_a_stock_english_kokoro_voice():
    assert {v.voice_id for v in POOL} <= _ENGLISH_STOCK_VOICES


@pytest.mark.unit
def test_pool_voices_and_names_are_unique():
    assert len({v.voice_id for v in POOL}) == len(POOL)
    assert len({v.spoken_name.lower() for v in POOL}) == len(POOL)


@pytest.mark.unit
def test_pool_never_contains_hope_or_atlas_default_voices():
    ids = {v.voice_id for v in POOL}
    assert "af_heart" not in ids
    assert "af_bella" not in ids


@pytest.mark.unit
def test_lease_hands_out_best_voice_first():
    assert VoicePool().lease() == POOL[0]


@pytest.mark.unit
def test_consecutive_leases_are_distinct():
    pool = VoicePool()
    first, second = pool.lease(), pool.lease()
    assert first.voice_id != second.voice_id


@pytest.mark.unit
def test_consecutive_leases_alternate_gender_prefix():
    pool = VoicePool()
    first, second = pool.lease(), pool.lease()
    assert first.voice_id[1] != second.voice_id[1]  # 'f' then 'm'


@pytest.mark.unit
def test_reserved_voice_is_never_leased():
    pool = VoicePool(reserved={POOL[0].voice_id})
    assert all(pool.lease().voice_id != POOL[0].voice_id for _ in range(pool.available()))


@pytest.mark.unit
def test_exhausted_pool_raises_instead_of_sharing_a_voice():
    pool = VoicePool(pool=(PooledVoice("af_nicole", "Nicole"),))
    pool.lease()
    with pytest.raises(VoicePoolExhausted):
        pool.lease()


@pytest.mark.unit
def test_released_voice_can_be_leased_again():
    pool = VoicePool(pool=(PooledVoice("af_nicole", "Nicole"),))
    voice = pool.lease()
    pool.release("nicole")  # case-insensitive, as it arrives from STT
    assert pool.lease() == voice


@pytest.mark.unit
def test_available_counts_down_and_back_up():
    pool = VoicePool()
    total = pool.available()
    voice = pool.lease()
    assert pool.available() == total - 1
    pool.release(voice.spoken_name)
    assert pool.available() == total
