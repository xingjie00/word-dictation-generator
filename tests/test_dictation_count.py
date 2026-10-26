# tests/test_dictation_count.py
# 抽查次数（dictation_count）：旧库迁移、计数写回、按次数加权选词
import json
import random
import sqlite3
from collections import Counter

import pytest

import src.db as db
from src.word_selector import select_words
from src.gui.main_window import write_document_and_record

SEED = {"word_list": [
    {"unit": "U1", "words": [
        {"word": "a", "translation": "甲"},
        {"word": "b", "translation": "乙"},
        {"word": "c", "translation": "丙"},
    ]},
]}

# 迁移前的旧表结构（无 dictation_count 列）
_OLD_SCHEMA = """
CREATE TABLE units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    word TEXT NOT NULL,
    translation TEXT NOT NULL,
    UNIQUE(unit_id, word)
);
"""


def _seed_file(tmp_path):
    f = tmp_path / "seed.json"
    f.write_text(json.dumps(SEED, ensure_ascii=False), encoding='utf-8')
    return str(f)


def _make_old_db(path):
    """手工建旧结构库并写入数据（模拟升级前的存量库）。"""
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_OLD_SCHEMA)
        conn.execute("INSERT INTO units (name) VALUES ('U1')")
        conn.execute(
            "INSERT INTO words (unit_id, word, translation) VALUES (1, 'a', '甲')"
        )
        conn.commit()
    finally:
        conn.close()


def _counts(path):
    """{word: dictation_count}（按 id 顺序，要求列已存在）。"""
    conn = db._connect(path)
    try:
        rows = conn.execute(
            "SELECT word, dictation_count FROM words ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    return dict(rows)


# ── 迁移 ───────────────────────────────────────────────────────────────

def test_migration_adds_column_preserves_data(tmp_path):
    """旧库启动自动补列：数据零丢失，dictation_count 默认 0。"""
    d = str(tmp_path / "words.db")
    _make_old_db(d)
    db.init_db(d, seed_json=_seed_file(tmp_path))  # units 非空 → 不重播种子
    assert _counts(d) == {'a': 0}
    data = db.load_word_data(d)
    assert data['unit_words']['U1'][0] == {
        'id': 1, 'word': 'a', 'translation': '甲', 'dictation_count': 0
    }


def test_migration_idempotent(tmp_path):
    """迁移幂等：连续两次 init 不报错、列不重复、数据不变。"""
    d = str(tmp_path / "words.db")
    _make_old_db(d)
    f = _seed_file(tmp_path)
    db.init_db(d, seed_json=f)
    db.init_db(d, seed_json=f)
    conn = db._connect(d)
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(words)")]
    finally:
        conn.close()
    assert cols.count('dictation_count') == 1
    assert _counts(d) == {'a': 0}


def test_new_db_has_column(tmp_path):
    """新建库：schema 自带列；查询接口均带出新字段。"""
    d = str(tmp_path / "words.db")
    db.init_db(d, seed_json=_seed_file(tmp_path))
    data = db.load_word_data(d)
    assert all(w['dictation_count'] == 0 for w in data['unit_words']['U1'])
    words = db.get_unit_words('U1', db_path=d)
    assert all('dictation_count' in w and 'id' in w for w in words)


# ── increment_dictation_counts ─────────────────────────────────────────

def test_increment_batch_and_duplicates(tmp_path):
    """批量 +1；同一 id 出现多次按次累加；空列表为 no-op。"""
    d = str(tmp_path / "words.db")
    db.init_db(d, seed_json=_seed_file(tmp_path))
    db.increment_dictation_counts([1, 2], db_path=d)
    db.increment_dictation_counts([1, 1], db_path=d)
    assert _counts(d) == {'a': 3, 'b': 1, 'c': 0}
    db.increment_dictation_counts([], db_path=d)
    assert _counts(d) == {'a': 3, 'b': 1, 'c': 0}


def test_increment_rolls_back_on_failure(tmp_path):
    """事务性：批量更新中途失败 → 整体回滚，计数不变。"""
    d = str(tmp_path / "words.db")
    db.init_db(d, seed_json=_seed_file(tmp_path))
    # 触发器模拟更新 id=2 时的数据库故障
    conn = db._connect(d)
    try:
        conn.execute(
            "CREATE TRIGGER boom BEFORE UPDATE ON words "
            "WHEN NEW.id = 2 BEGIN SELECT RAISE(ABORT, 'boom'); END"
        )
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(sqlite3.Error):
        db.increment_dictation_counts([1, 2, 3], db_path=d)
    assert _counts(d) == {'a': 0, 'b': 0, 'c': 0}  # id=1 的更新同样被回滚


# ── 加权选词 ───────────────────────────────────────────────────────────

def _single_unit_data(counts):
    """构造单单元数据：词 w0/w1/...，dictation_count 取 counts。"""
    words = [
        {'word': f'w{i}', 'translation': f'词{i}', 'dictation_count': c}
        for i, c in enumerate(counts)
    ]
    return {'units': ['U'], 'unit_words': {'U': words}}


def test_weighted_selection_favors_low_count():
    """权重 1/(count+1)：次数 0 的词中选频率显著高于次数 5 的词。"""
    data = _single_unit_data([0, 0, 5])
    plans = select_words(data, [], ['U'], 0, 1, 3000, rng=random.Random(42))
    counter = Counter(w.word for p in plans for w in p.review_words)
    # 权重比 1 : 1 : 1/6 → 期望 w0≈w1≈6×w2
    assert counter['w0'] > 4 * counter['w2']
    assert counter['w1'] > 4 * counter['w2']
    assert sum(counter.values()) == 3000
    # 入选词条透传 dictation_count
    assert all(w.dictation_count == 5
               for p in plans for w in p.review_words if w.word == 'w2')


def test_all_zero_behaves_uniform():
    """全 0（含缺失键的旧格式数据）→ 等权，分布与均匀随机一致。"""
    data = _single_unit_data([0, 0, 0])
    # 缺失 dictation_count 键 → 视为 0（向后兼容）
    data['unit_words']['U'].append({'word': 'w3', 'translation': '词3'})
    plans = select_words(data, [], ['U'], 0, 1, 4000, rng=random.Random(42))
    counter = Counter(w.word for p in plans for w in p.review_words)
    assert set(counter) == {'w0', 'w1', 'w2', 'w3'}
    # 4 词等权 → 期望各 1000（固定 seed 下为确定性验证，带宽远宽于波动）
    assert all(750 < c < 1250 for c in counter.values())
    assert all(w.dictation_count == 0 for p in plans for w in p.review_words)


# ── 写回时机 ───────────────────────────────────────────────────────────

def test_record_after_successful_write(tmp_path):
    """写盘成功 → 文档入选词计数各 +1（跨天、重点/复习都计）。"""
    d = str(tmp_path / "words.db")
    db.init_db(d, seed_json=_seed_file(tmp_path))
    data = db.load_word_data(d)
    plans = select_words(data, ['U1'], ['U1'], 1, 1, 2, rng=random.Random(42))

    html = '<html></html>'
    out = tmp_path / "doc.html"
    write_document_and_record(str(out), html, plans, db_path=d)

    assert out.read_text(encoding='utf-8') == html
    # 2 天 ×（1 重点 + 1 复习）= 4 次入选；词 id 正确透传才会累计
    assert sum(_counts(d).values()) == 4


def test_no_record_when_write_fails(tmp_path):
    """写盘失败（目标为目录）→ 计数不变。"""
    d = str(tmp_path / "words.db")
    db.init_db(d, seed_json=_seed_file(tmp_path))
    data = db.load_word_data(d)
    plans = select_words(data, [], ['U1'], 0, 3, 1, rng=random.Random(42))
    with pytest.raises(OSError):
        write_document_and_record(str(tmp_path), '<html></html>', plans, db_path=d)
    assert _counts(d) == {'a': 0, 'b': 0, 'c': 0}
