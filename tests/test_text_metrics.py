from eng_essay_qgen.text_metrics import count_words, find_ngram_matches, has_placeholder, tokenize


def test_apostrophes_and_hyphenated_words_count_as_one():
    text = "Mirror's answer changed; don't copy well-known ideas or 2026-08 plans."
    assert tokenize(text) == [
        "Mirror's",
        "answer",
        "changed",
        "don't",
        "copy",
        "well-known",
        "ideas",
        "or",
        "2026-08",
        "plans",
    ]
    assert count_words(text) == 10


def test_ngram_match_reports_positions_and_respects_whitelist():
    passage = "People often tell a white lie to protect their friends from pain."
    answer = "They may tell a white lie to."
    matches = find_ngram_matches(passage, answer, n=5)
    assert any(item["phrase"] == "tell a white lie to" for item in matches)
    assert find_ngram_matches(passage, answer, n=5, whitelist=["tell a white lie to"]) == []


def test_placeholder_detection_is_conservative():
    assert has_placeholder("Use {{condition_1}} here.")
    assert has_placeholder("TODO: revise")
    assert not has_placeholder("Students should explain the condition clearly.")
