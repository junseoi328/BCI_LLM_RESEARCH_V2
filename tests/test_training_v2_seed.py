from training_v2.common import extract_initials, normalize_text
from training_v2.seed_inventory import SEED_BLOCKS


def test_seed_inventory_initials_not_empty():
    for block in SEED_BLOCKS:
        for phrase in block["phrases"]:
            assert extract_initials(phrase)


def test_seed_inventory_no_normalized_duplicate():
    seen = set()
    for block in SEED_BLOCKS:
        for phrase in block["phrases"]:
            key = normalize_text(phrase)
            assert key not in seen
            seen.add(key)


def test_ambiguity_has_collisions():
    groups = {}
    for block in SEED_BLOCKS:
        for phrase in block["phrases"]:
            groups.setdefault(extract_initials(phrase), []).append(phrase)
    assert sum(len(v) >= 3 for v in groups.values()) >= 8
