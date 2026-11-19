# tests/test_save_split.py
# split_new_and_existing：保存到已有单元时的精确匹配拆分逻辑
from src.gui.tabs.word_library import split_new_and_existing


def test_mixed_split_preserves_order():
    """已存在项进 skipped、新词进 to_save，两侧各自保持原顺序。"""
    staging = [('across', '在对面'), ('across from', '在对面'),
               ('apple', '苹果'), ('book', '书')]
    existing = {'across', 'book'}
    to_save, skipped = split_new_and_existing(staging, existing)
    assert to_save == [('across from', '在对面'), ('apple', '苹果')]
    assert skipped == [('across', '在对面'), ('book', '书')]


def test_all_existing_yields_empty_to_save():
    """全部已存在：to_save 为空（调用方据此不写库）。"""
    staging = [('each', '每个'), ('each other', '互相')]
    to_save, skipped = split_new_and_existing(staging, {'each', 'each other'})
    assert to_save == []
    assert skipped == [('each', '每个'), ('each other', '互相')]


def test_none_existing_yields_empty_skipped():
    """全部为新词：skipped 为空，to_save 原样保序。"""
    staging = [('a', '甲'), ('b', '乙')]
    to_save, skipped = split_new_and_existing(staging, set())
    assert to_save == [('a', '甲'), ('b', '乙')]
    assert skipped == []


def test_empty_staging():
    """空暂存：两侧均为空。"""
    assert split_new_and_existing([], {'a'}) == ([], [])


def test_exact_match_not_substring():
    """精确匹配：each 与 each other 互不误判（in 判定基于集合哈希相等）。"""
    staging = [('each', '每个'), ('each other', '互相'),
               ('teach', '教'), ('teacher', '教师')]
    to_save, skipped = split_new_and_existing(staging, {'each'})
    assert [w for w, _ in to_save] == ['each other', 'teach', 'teacher']
    assert skipped == [('each', '每个')]


def test_duplicate_word_within_staging_goes_where_it_matches():
    """暂存内部重复词与库中已存在词一致时：两条都进 skipped（逐条独立判定）。"""
    staging = [('apple', '苹果'), ('apple', '苹果2')]
    to_save, skipped = split_new_and_existing(staging, {'apple'})
    assert to_save == []
    assert skipped == [('apple', '苹果'), ('apple', '苹果2')]
