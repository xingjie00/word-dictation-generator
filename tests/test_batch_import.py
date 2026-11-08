# tests/test_batch_import.py
import json

import src.db as db
from src.gui.tabs.word_library import build_export_data, parse_batch_text


def test_basic_parse_with_mixed_separators():
    """空格 / Tab / 中英文逗号 / 分号均可作为分隔符。"""
    entries, errors = parse_batch_text("apple 苹果\nbook\t书\ncat,猫\ndog；狗")
    assert entries == [('apple', '苹果'), ('book', '书'), ('cat', '猫'), ('dog', '狗')]
    assert errors == []


def test_missing_translation_reported():
    """只有英文没有释义的行报「缺少释义」，其余行正常解析。"""
    entries, errors = parse_batch_text("apple\nbook 书")
    assert entries == [('book', '书')]
    assert errors == [(1, '缺少释义')]


def test_intra_batch_duplicate_keeps_first():
    """批内英文单词重复时保留首个，后续行计入错误。"""
    entries, errors = parse_batch_text("apple 苹果\napple 苹果2\napple 苹果3")
    assert entries == [('apple', '苹果')]
    assert len(errors) == 2
    assert all('批内重复' in r for _, r in errors)


def test_blank_lines_skipped():
    """空行与纯空白行被忽略，不报错。"""
    entries, errors = parse_batch_text("\n  \napple 苹果\n\t\n")
    assert entries == [('apple', '苹果')]
    assert errors == []


def test_translation_keeps_rest_of_line():
    """释义可含空格/标点（首个分隔符后的全部内容作为释义）。"""
    entries, _ = parse_batch_text("apple n. 苹果, 一种水果")
    assert entries == [('apple', 'n. 苹果, 一种水果')]


def test_translation_whitespace_normalized():
    """释义内的连续空白规整为单个空格。"""
    entries, _ = parse_batch_text("apple  n.   苹果")
    assert entries == [('apple', 'n. 苹果')]


def test_word_stripped():
    """英文单词两侧的空白被去除。"""
    entries, _ = parse_batch_text("  apple   苹果  ")
    assert entries == [('apple', '苹果')]


def test_empty_text_yields_nothing():
    """空文本 → 无条目、无错误。"""
    entries, errors = parse_batch_text("")
    assert entries == [] and errors == []


def test_build_export_data_strips_runtime_fields():
    """导出结构只保留 unit/word/translation，丢弃 id 与 dictation_count。"""
    data = {'units': ['U1', 'U2'], 'unit_words': {
        'U1': [{'id': 1, 'word': 'a', 'translation': '甲', 'dictation_count': 3},
               {'id': 2, 'word': 'b', 'translation': '乙', 'dictation_count': 0}],
        'U2': [],
    }}
    export = build_export_data(data)
    assert export == {'word_list': [
        {'unit': 'U1', 'words': [{'word': 'a', 'translation': '甲'},
                                 {'word': 'b', 'translation': '乙'}]},
        {'unit': 'U2', 'words': []},
    ]}


def test_export_round_trip_as_seed(tmp_path):
    """导出的 JSON 可直接作为种子文件重建词库（格式与 words.json 同构）。"""
    d = str(tmp_path / "words.db")
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps({"word_list": [
        {"unit": "U1", "words": [{"word": "a", "translation": "甲"}]},
    ]}, ensure_ascii=False), encoding='utf-8')
    db.init_db(d, seed_json=str(seed))

    export_path = tmp_path / "export.json"
    with open(export_path, 'w', encoding='utf-8') as f:
        json.dump(build_export_data(db.load_word_data(d)), f,
                  ensure_ascii=False, indent=2)

    d2 = str(tmp_path / "words2.db")
    db.init_db(d2, seed_json=str(export_path))
    data = db.load_word_data(d2)
    assert data['units'] == ['U1']
    assert [w['word'] for w in data['unit_words']['U1']] == ['a']
