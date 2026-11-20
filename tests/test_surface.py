"""B3: no cheap surface feature may separate erroneous documents from correct ones on its own.

300 episodes over all open configs; for each feature and for each error type (and all types
together) precision and recall must not BOTH exceed 0.6. The table is in docs/LIMITATIONS.md
(regenerate: python -m auditenv analyze --n 300).
"""

import pytest

from auditenv.analysis import FEATURES, THRESHOLD, generate_many, plan, shortcuts, surface_table


@pytest.fixture(scope="module")
def results():
    return generate_many(plan(300))


@pytest.mark.slow
def test_no_surface_feature_is_a_shortcut(results):
    table = surface_table(results)
    assert {f for f, _ in table} == set(FEATURES)
    assert shortcuts(table) == []


@pytest.mark.slow
def test_detector_catches_a_planted_shortcut(results):
    """Sanity: label documents by a feature itself -> the detector must flag it."""
    from auditenv.env.data import PublicData
    from auditenv.analysis import doc_features

    planted = []
    for cfg, seed, files, truth, muts in results[:40]:
        feats = doc_features(PublicData(files))
        fake = [{"type": "fx_rate", "affected_ids": [k]} for k, f in feats.items() if f["utc_format"]]
        planted.append((cfg, seed, files, {"issues": fake}, muts))
    assert ("utc_format", "any") in shortcuts(surface_table(planted))


def test_threshold_is_the_documented_one():
    assert THRESHOLD == 0.6
