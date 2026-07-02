from plexget.filtering import filter_items


def test_empty_query_returns_all_in_order():
    assert filter_items(["b", "a", "c"], "") == ["b", "a", "c"]


def test_subsequence_match_case_insensitive():
    items = ["Severance", "Silo", "Succession", "The Bear"]
    # "sev" is a subsequence of Severance only
    assert filter_items(items, "sev") == ["Severance"]
    # "sc" is a subsequence of Su(c)cession and also... check ordering preserved
    assert filter_items(items, "sc") == ["Severance", "Succession"]


def test_non_contiguous_subsequence_matches():
    assert filter_items(["Season 1", "Season 12"], "s1") == ["Season 1", "Season 12"]


def test_key_extractor_used():
    items = [{"name": "Alpha"}, {"name": "Beta"}]
    assert filter_items(items, "bt", key=lambda d: d["name"]) == [{"name": "Beta"}]
