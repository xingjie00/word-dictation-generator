# tests/test_db.py
# 全部用例使用 tmp_path + 显式 db_path/seed_json，绝不触碰真实 resources/
import json
import os
import random
import sqlite3

import pytest

import src.db as db
from src.word_selector import select_words

SEED = {"word_list": [
    {"unit": "U1", "words": [
        {"word": "a", "translation": "甲"},
        {"word": "b", "translation": "乙"},
    ]},
    {"unit": "U2", "words": [
        {"word": "c", "translation": "丙"},
    ]},
]}


def _seed_file(tmp_path):
    f = tmp_path / "seed.json"
    f.write_text(json.dumps(SEED, ensure_ascii=False), encoding='utf-8')
    return str(f)


def test_first_run_import(tmp_path):
    """首次导入：init_db(seed) → load → 数据正确，无 word_list 键。"""
    d = str(tmp_path / "words.db")
    f = _seed_file(tmp_path)
    db.init_db(d, seed_json=f)
    data = db.load_word_data(d)
    assert data['units'] == ['U1', 'U2']
    assert data['unit_words']['U1'] == [
        {'word': 'a', 'translation': '甲'},
        {'word': 'b', 'translation': '乙'},
    ]
    assert data['unit_words']['U2'] == [{'word': 'c', 'translation': '丙'}]
    assert 'word_list' not in data


def test_init_idempotent(tmp_path):
    """幂等：init_db×2 → 数据不翻倍。"""
    d = str(tmp_path / "words.db")
    f = _seed_file(tmp_path)
    db.init_db(d, seed_json=f)
    db.init_db(d, seed_json=f)
    data = db.load_word_data(d)
    assert data['units'] == ['U1', 'U2']
    assert len(data['unit_words']['U1']) == 2


def test_no_reseed_when_data_exists(tmp_path):
    """已有数据时不重播种子。"""
    d = str(tmp_path / "words.db")
    f = _seed_file(tmp_path)
    db.init_db(d, seed_json=f)
    db.add_unit('U3', [('x', '叉')], db_path=d)
    db.init_db(d, seed_json=f)  # 再初始化不应覆盖/重复
    data = db.load_word_data(d)
    assert 'U3' in data['units']
    assert data['units'].count('U1') == 1  # 种子不重复导入


def test_add_unit_appends_at_end(tmp_path):
    """add_unit 追加到单元列表尾部。"""
    d = str(tmp_path / "words.db")
    db.init_db(d, seed_json=_seed_file(tmp_path))
    assert db.add_unit('U3', [('x', '叉')], db_path=d) is True
    data = db.load_word_data(d)
    assert data['units'] == ['U1', 'U2', 'U3']
    assert data['unit_words']['U3'] == [{'word': 'x', 'translation': '叉'}]


def test_add_unit_duplicate_name_returns_false(tmp_path):
    """重复单元名：返回 False，原数据不变。"""
    d = str(tmp_path / "words.db")
    db.init_db(d, seed_json=_seed_file(tmp_path))
    assert db.add_unit('U1', [('z', '子')], db_path=d) is False
    data = db.load_word_data(d)
    assert len(data['unit_words']['U1']) == 2  # 'z' 未插入


def test_add_words_to_early_unit_preserves_order(tmp_path):
    """向早期单元追加词保序（两表设计的关键用例）。"""
    d = str(tmp_path / "words.db")
    db.init_db(d, seed_json=_seed_file(tmp_path))
    db.add_words('U1', [('d', '丁')], db_path=d)
    data = db.load_word_data(d)
    assert data['units'] == ['U1', 'U2']  # U2 仍在 U1 之后
    assert [w['word'] for w in data['unit_words']['U1']] == ['a', 'b', 'd']  # d 跟在 b 后


def test_add_words_missing_unit_returns_false(tmp_path):
    """向不存在的单元加词返回 False。"""
    d = str(tmp_path / "words.db")
    db.init_db(d, seed_json=_seed_file(tmp_path))
    assert db.add_words('UX', [('x', '叉')], db_path=d) is False


def test_unique_and_fk_constraints(tmp_path):
    """UNIQUE 兜底 + PRAGMA foreign_keys 生效。"""
    d = str(tmp_path / "words.db")
    db.init_db(d, seed_json=_seed_file(tmp_path))
    conn = db._connect(d)
    try:
        # 重复 (unit_id, word) → IntegrityError
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO words (unit_id, word, translation) "
                "VALUES ((SELECT id FROM units WHERE name='U1'), 'a', '重复')"
            )
        # 伪 unit_id → 外键约束（证明 PRAGMA foreign_keys=ON 生效）
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO words (unit_id, word, translation) VALUES (99999, 'zz', '伪')"
            )
    finally:
        conn.close()


def test_corrupt_file_self_heal(tmp_path):
    """损坏自愈：垃圾字节 → 隔离 + 重建 + 种子数据可加载。"""
    d = str(tmp_path / "words.db")
    f = _seed_file(tmp_path)
    with open(d, 'wb') as fh:
        fh.write(b'this is not a database at all')
    quarantine = db.init_db(d, seed_json=f)
    assert quarantine is not None
    assert os.path.exists(quarantine)
    data = db.load_word_data(d)
    assert data['units'] == ['U1', 'U2']


def test_seed_missing_raises(tmp_path):
    """种子缺失：RuntimeError（中文消息含 words.json）。"""
    d = str(tmp_path / "words.db")
    with pytest.raises(RuntimeError) as exc:
        db.init_db(d, seed_json=str(tmp_path / "nope.json"))
    assert 'words.json' in str(exc.value)


def test_query_helpers(tmp_path):
    """unit_exists / get_unit_words / get_unit_names 基础断言。"""
    d = str(tmp_path / "words.db")
    db.init_db(d, seed_json=_seed_file(tmp_path))
    assert db.unit_exists('U1', db_path=d) is True
    assert db.unit_exists('UX', db_path=d) is False
    assert db.get_unit_names(db_path=d) == ['U1', 'U2']
    assert db.get_unit_words('U2', db_path=d) == [{'word': 'c', 'translation': '丙'}]
    assert db.get_unit_words('UX', db_path=d) == []


def test_selector_integration(tmp_path):
    """选择器集成：db.load_word_data 输出对未改动的 word_selector 即插即用。"""
    d = str(tmp_path / "words.db")
    db.init_db(d, seed_json=_seed_file(tmp_path))
    data = db.load_word_data(d)
    plans = select_words(data, ['U1'], ['U2'], focus_count=2, review_count=1, days=1,
                         rng=random.Random(42))
    assert len(plans) == 1
    all_words = [w.word for w in plans[0].focus_words] + [w.word for w in plans[0].review_words]
    assert len(all_words) == 3
    assert len(all_words) == len(set(all_words))  # 无重复


def test_seed_intra_unit_duplicate_keeps_first(tmp_path):
    """种子单元内重复词保留首个（first-wins，与选词语义一致）。"""
    seed = {"word_list": [
        {"unit": "U1", "words": [
            {"word": "a", "translation": "甲1"},
            {"word": "a", "translation": "甲2"},  # 单元内重复
            {"word": "b", "translation": "乙"},
        ]},
    ]}
    f = tmp_path / "dup.json"
    f.write_text(json.dumps(seed, ensure_ascii=False), encoding='utf-8')
    d = str(tmp_path / "words.db")
    db.init_db(d, seed_json=str(f))
    data = db.load_word_data(d)
    assert [w['word'] for w in data['unit_words']['U1']] == ['a', 'b']
    assert data['unit_words']['U1'][0]['translation'] == '甲1'
