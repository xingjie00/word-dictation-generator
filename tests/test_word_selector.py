# tests/test_word_selector.py
import random
from collections import Counter

import pytest

from src.word_selector import select_words, SelectionError

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


def test_translation_matches_unit():
    """共享词的释义与所归属的单元一致（抽到哪个单元就用哪个单元的释义）。"""
    plans = select_words(
        SAMPLE_DATA, [], ['U1', 'U2'],
        focus_count=0, review_count=2, days=1,
        rng=random.Random(0)
    )
    for w in plans[0].review_words:
        if w.word == 'right':
            expected = '好的' if w.unit == 'U1' else '右边'
            assert w.translation == expected


def test_two_stage_all_units_represented():
    """名额 ≥ 单元数时，每个选中单元当天都至少贡献 1 词。"""
    data = {
        'units': ['U1', 'U2', 'U3'],
        'unit_words': {
            f'U{i}': [{'word': f'u{i}w{j}', 'translation': f'词{i}-{j}'}
                      for j in range(5)]
            for i in range(1, 4)
        },
        'word_list': []
    }
    plans = select_words(data, [], ['U1', 'U2', 'U3'],
                         0, 15, 1, rng=random.Random(3))
    words = [w.word for w in plans[0].review_words]
    units_seen = {w.unit for w in plans[0].review_words}
    assert units_seen == {'U1', 'U2', 'U3'}
    assert len(words) == len(set(words)) == 15  # 无重复且填满


def test_two_stage_weighted_favor_large_unit():
    """剩余名额按单元词量加权：大单元贡献显著更多。"""
    data = {
        'units': ['A', 'B'],
        'unit_words': {
            'A': [{'word': f'a{i}', 'translation': f'甲{i}'} for i in range(20)],
            'B': [{'word': f'b{i}', 'translation': f'乙{i}'} for i in range(2)],
        },
        'word_list': []
    }
    plans = select_words(data, [], ['A', 'B'], 0, 12, 1, rng=random.Random(5))
    counts = Counter(w.unit for w in plans[0].review_words)
    assert counts['A'] >= 10  # B 全部仅 2 词，A 至少分得 10 个名额


def test_two_stage_fewer_slots_than_units():
    """名额 < 单元数时，名额随机集中到部分单元（不保底，允许集中）。"""
    data = {
        'units': ['U1', 'U2', 'U3'],
        'unit_words': {
            f'U{i}': [{'word': f'u{i}w{j}', 'translation': f'词{i}-{j}'}
                      for j in range(4)]
            for i in range(1, 4)
        },
        'word_list': []
    }
    plans = select_words(data, [], ['U1', 'U2', 'U3'],
                         0, 2, 1, rng=random.Random(11))
    words = [w.word for w in plans[0].review_words]
    units_seen = {w.unit for w in plans[0].review_words}
    assert len(words) == len(set(words)) == 2  # 当天无重复
    assert units_seen <= {'U1', 'U2', 'U3'}


def test_shared_words_spread_across_units():
    """两个单元含完全相同的词：每词整周期仅一次，但两个单元都获得名额归属。"""
    data = {
        'units': ['S', 'T'],
        'unit_words': {
            'S': [{'word': w, 'translation': f'S-{w}'} for w in ('a', 'b', 'c')],
            'T': [{'word': w, 'translation': f'T-{w}'} for w in ('a', 'b', 'c')],
        },
        'word_list': []
    }
    plans = select_words(data, [], ['S', 'T'], 0, 3, 1, rng=random.Random(2))
    words = [w.word for w in plans[0].review_words]
    units_seen = {w.unit for w in plans[0].review_words}
    assert sorted(words) == ['a', 'b', 'c']  # 每词恰好一次
    assert units_seen == {'S', 'T'}  # 不再被首个单元垄断


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
    """focus 当天占用共享词后 review 不足 → 当日检查抛 SelectionError。"""
    # 构造数据：focus 与 review 共享词 'right'
    # focus_pool = {apple, right}; review_pool = {right, book}
    # focus 当天消耗 apple + right; review 需 2 但当天只剩 book = 1
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


def test_focus_review_same_day_disjoint():
    """同一天内重点与复习不重复：重点当天选走的词，复习不再出现。"""
    data = {
        'units': ['F1', 'R1'],
        'unit_words': {
            'F1': [{'word': 'fx', 'translation': '甲'}, {'word': 'fy', 'translation': '乙'}],
            'R1': [{'word': 'fx', 'translation': '甲'}, {'word': 'r1', 'translation': '丙'},
                   {'word': 'r2', 'translation': '丁'}],
        },
        'word_list': []
    }
    plans = select_words(data, ['F1'], ['R1'],
                         focus_count=2, review_count=2, days=1,
                         rng=random.Random(0))
    day_words = ([w.word for w in plans[0].focus_words]
                 + [w.word for w in plans[0].review_words])
    assert len(day_words) == len(set(day_words)) == 4  # 当天全不重复
    assert 'fx' not in [w.word for w in plans[0].review_words]


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


def test_within_day_unique_cross_day_repeat_allowed():
    """当天不重复；跨天允许重复——池小于总需求时也照常生成。"""
    data = {
        'units': ['R'],
        'unit_words': {
            'R': [{'word': f'r{i}', 'translation': f'词{i}'} for i in range(4)],
        },
        'word_list': []
    }
    # 池仅 4 词，3 天 × 4 词/天 = 12 次抽取必然跨天重复，但不应报错
    plans = select_words(data, [], ['R'], 0, 4, 3, rng=random.Random(1))
    for p in plans:
        words = [w.word for w in p.review_words]
        assert len(words) == len(set(words)) == 4  # 每天内部无重复
    all_words = [w.word for p in plans for w in p.review_words]
    assert len(all_words) == 12 and len(set(all_words)) == 4  # 跨天重复发生


def test_zero_counts_ok():
    """focus_count=0, review_count=0 → 不报错，返回空计划。"""
    plans = select_words(SAMPLE_DATA, [], [], 0, 0, 3, rng=random.Random(0))
    assert all(len(p.focus_words) == 0 and len(p.review_words) == 0 for p in plans)


def test_multi_day_with_focus():
    """多天 + 重点 + 复习：每天内部无重复，数量正确。"""
    data = {
        'units': ['A', 'B'],
        'unit_words': {
            'A': [{'word': f'w{i}', 'translation': f'词{i}'} for i in range(10)],
            'B': [{'word': f'v{i}', 'translation': f'义{i}'} for i in range(10)],
        },
        'word_list': []
    }
    plans = select_words(data, ['A'], ['B'], focus_count=2, review_count=3, days=3, rng=random.Random(7))
    for p in plans:
        assert len(p.focus_words) == 2 and len(p.review_words) == 3
        day_words = ([w.word for w in p.focus_words]
                     + [w.word for w in p.review_words])
        assert len(day_words) == len(set(day_words))  # 当天无重复
    assert len(plans) == 3
