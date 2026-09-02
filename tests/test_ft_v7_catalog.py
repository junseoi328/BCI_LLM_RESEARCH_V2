from training.catalog import TRAIN_GROUPS, DEV_GROUPS
from training.common import extract_initials, normalize_text


def test_catalog_initials_exact():
    for initials, candidates in {**TRAIN_GROUPS, **DEV_GROUPS}.items():
        for text in candidates:
            assert extract_initials(text) == initials


def test_train_dev_groups_disjoint():
    assert not (set(TRAIN_GROUPS) & set(DEV_GROUPS))


def test_no_normalized_duplicates_inside_group():
    for candidates in list(TRAIN_GROUPS.values()) + list(DEV_GROUPS.values()):
        keys = [normalize_text(x) for x in candidates]
        assert len(keys) == len(set(keys))
