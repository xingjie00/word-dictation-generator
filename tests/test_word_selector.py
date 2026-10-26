# tests/test_word_selector.py
import random
import pytest

from src.word_selector import select_words, SelectionError, WordEntry, DayPlan, _build_pool

SAMPLE_DATA = {
    'units': ['U1', 'U2', 'U3'],
    'unit_words': {
        'U1': [{'word': 'apple', 'translation': '苹果'}, {'word': 'right', 'translation': '好的'}],
        'U2': [{'word': 'right', 'translation': '右边'}, {'word': 'book', 'translation': '书'}],
        'U3': [{'word': 'cat', 'translation': '猫'}, {'word': 'dog', 'translation': '狗'}],
    },
    'word_list': []
}


def test_dedup_same_word_different_translation():
    """'right' 在 U1 和 U2 释义不同，严格去重后只出现一次。"""
    plans = select_words(
        SAMPLE_DATA, [], ['U1', 'U2'],
        focus_count=0, review_count=2, days=1,
        rng=random.Random(0)
    )
    words = [w.word for p in plans for w in p.review_words]
    assert words.count('right') <= 1


def test_build_pool_first_translation_wins():
    """_build_pool 中同一单词首次出现的释义胜出。"""
    pool = _build_pool(SAMPLE_DATA, ['U1', 'U2'])
    right_entry = next(w for w in pool if w.word == 'right')
    assert right_entry.translation == '好的'  # U1 的释义


def test_insufficient_focus_raises():
    """重点单词不足时抛 SelectionError。"""
    with pytest.raises(SelectionError) as exc:
        select_words(SAMPLE_DATA, ['U1'], [], focus_count=5, review_count=0, days=1)
    assert '重点' in str(exc.value)


def test_insufficient_review_raises():
    """复习单词不足时抛 SelectionError。"""
    with pytest.raises(SelectionError) as exc:
        select_words(SAMPLE_DATA, [], ['U3'], focus_count=0, review_count=5, days=1)
    assert '复习' in str(exc.value)


def test_cross_pool_depletion_raises():
    """focus 消耗共享词后 review 不足 → 每日检查抛 SelectionError。"""
    # 构造数据：focus 与 review 共享词 'right'
    # focus_pool = {apple, right}; review_pool = {right, book}
    # focus 2/day × 1 day 消耗 apple + right; review 需 2 但只剩 book = 1
    data = {
        'units': ['F1', 'R1'],
        'unit_words': {
            'F1': [{'word': 'apple', 'translation': '苹果'}, {'word': 'right', 'translation': '好的'}],
            'R1': [{'word': 'right', 'translation': '右边'}, {'word': 'book', 'translation': '书'}],
        },
        'word_list': []
    }
    with pytest.raises(SelectionError):
        select_words(data, ['F1'], ['R1'], focus_count=2, review_count=2, days=1)


def test_seed_reproducibility():
    """同 seed 两次调用结果相同。"""
    p1 = select_words(SAMPLE_DATA, [], ['U1', 'U2', 'U3'], 0, 3, 1, rng=random.Random(42))
    p2 = select_words(SAMPLE_DATA, [], ['U1', 'U2', 'U3'], 0, 3, 1, rng=random.Random(42))
    assert [w.word for w in p1[0].review_words] == [w.word for w in p2[0].review_words]


def test_focus_review_separation():
    """重点词来自 focus_units，复习词来自 review_units。"""
    plans = select_words(
        SAMPLE_DATA, ['U1'], ['U3'],
        focus_count=1, review_count=1, days=1,
        rng=random.Random(0)
    )
    assert len(plans[0].focus_words) == 1 and plans[0].focus_words[0].unit == 'U1'
    assert len(plans[0].review_words) == 1 and plans[0].review_words[0].unit == 'U3'


def test_no_repeat_across_days():
    """3 天 × 1 词 → 所有词无重复。"""
    plans = select_words(
        SAMPLE_DATA, [], ['U1', 'U2', 'U3'],
        0, 1, 3, rng=random.Random(1)
    )
    all_words = [w.word for p in plans for w in p.review_words]
    assert len(all_words) == len(set(all_words))


def test_zero_counts_ok():
    """focus_count=0, review_count=0 → 不报错，返回空计划。"""
    plans = select_words(SAMPLE_DATA, [], [], 0, 0, 3, rng=random.Random(0))
    assert all(len(p.focus_words) == 0 and len(p.review_words) == 0 for p in plans)


def test_multi_day_with_focus():
    """多天 + 重点 + 复习，跨天无重复。"""
    data = {
        'units': ['A', 'B'],
        'unit_words': {
            'A': [{'word': f'w{i}', 'translation': f'词{i}'} for i in range(10)],
            'B': [{'word': f'v{i}', 'translation': f'义{i}'} for i in range(10)],
        },
        'word_list': []
    }
    plans = select_words(data, ['A'], ['B'], focus_count=2, review_count=3, days=3, rng=random.Random(7))
    all_words = []
    for p in plans:
        all_words.extend(w.word for w in p.focus_words)
        all_words.extend(w.word for w in p.review_words)
    assert len(all_words) == len(set(all_words))  # 无重复
    assert len(plans) == 3
