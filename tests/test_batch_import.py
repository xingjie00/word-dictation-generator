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


def test_phrase_split_at_cjk_boundary():
    """含空格的英文短语：中英分界由中文起点而非空格决定。"""
    entries, errors = parse_batch_text(
        "a lot of 很多\nthank you 谢谢你\nvery much 非常")
    assert entries == [('a lot of', '很多'),
                       ('thank you', '谢谢你'),
                       ('very much', '非常')]
    assert errors == []


def test_explicit_separators_and_no_hyphen_false_cut():
    """显式分隔符逐一生效；无空格连字符（well-known）不被误切。"""
    entries, errors = parse_batch_text(
        "well-known 著名的\nhello 你好\napple\t苹果\npear|梨\nplum：李子\n"
        "a lot of — 很多\ncat,猫\ndog;狗\nwin v. 胜利")
    assert entries == [
        ('well-known', '著名的'),
        ('hello', '你好'),
        ('apple', '苹果'),
        ('pear', '梨'),
        ('plum', '李子'),
        ('a lot of', '很多'),
        ('cat', '猫'),
        ('dog', '狗'),
        ('win', 'v. 胜利'),
    ]
    assert errors == []


def test_separator_after_cjk_is_not_a_separator():
    """分隔符出现在中文之后时只是释义内标点，不参与切分。"""
    entries, _ = parse_batch_text("apple 苹果, 一种水果")
    assert entries == [('apple', '苹果, 一种水果')]


def test_invalid_lines_reported_without_half_data():
    """只有英文 / 只有中文 / 中英倒置的行进入失败汇总，不产生半条数据。"""
    entries, errors = parse_batch_text("abc\n你好\napple\n苹果,香蕉")
    assert entries == []
    assert errors == [(1, '缺少释义'), (2, '缺少英文单词'),
                      (3, '缺少释义'), (4, '缺少英文单词')]


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


def test_multi_column_tab_merges_english_phrase():
    """多列 Tab 行（PDF/Excel 复制）：短语内含 Tab 时英文列归并回单词侧。"""
    entries, errors = parse_batch_text("across\tfrom\t在对面")
    assert entries == [('across from', '在对面')]
    assert errors == []


def test_multi_column_tab_pos_column_kept_in_translation():
    """多列 Tab 行中间是词性标注时：词性归入释义，单词侧不被污染。"""
    entries, errors = parse_batch_text("across\tprep.\t在对面")
    assert entries == [('across', 'prep. 在对面')]
    assert errors == []


def test_multi_column_tab_row_number_column_dropped():
    """带表格行号列的 Tab 行：行号被丢弃，不进入英文侧。"""
    entries, errors = parse_batch_text("1\tacross\t在对面")
    assert entries == [('across', '在对面')]
    assert errors == []


def test_two_column_tab_unchanged():
    """普通两列 Tab 行行为不变。"""
    entries, errors = parse_batch_text("apple\t苹果\nacross from\t在对面")
    assert entries == [('apple', '苹果'), ('across from', '在对面')]
    assert errors == []


def test_multi_column_tab_extra_zh_columns_joined():
    """多列释义：全部中文列合并为一条释义。"""
    entries, errors = parse_batch_text("book\t书\t课本")
    assert entries == [('book', '书 课本')]
    assert errors == []


def test_non_tab_separator_takes_priority_over_tab_split():
    """最左显式分隔符不是 Tab（如竖线）时交回原有规则，Tab 只是释义内空白。"""
    entries, errors = parse_batch_text("across|from\t在对面")
    assert entries == [('across', 'from 在对面')]
    assert errors == []


def test_leading_tab_column_stripped():
    """行首 Tab（复制表格时常见）：空列被去除后正常解析。"""
    entries, errors = parse_batch_text("\tacross\t中文")
    assert entries == [('across', '中文')]
    assert errors == []


def test_no_tab_lines_still_use_original_rules():
    """无 Tab 行回归抽查：空格分隔与短语切分不受多列逻辑影响。"""
    entries, errors = parse_batch_text("apple 苹果\na lot of 很多")
    assert entries == [('apple', '苹果'), ('a lot of', '很多')]
    assert errors == []


def test_multi_column_tab_mixed_with_normal_lines():
    """多列 Tab 行与普通行混排：逐行独立解析。"""
    entries, errors = parse_batch_text(
        "across\tfrom\t在对面\napple 苹果\nbook\t书")
    assert entries == [('across from', '在对面'),
                       ('apple', '苹果'),
                       ('book', '书')]
    assert errors == []


def test_tab_inside_phrase_merges_ascii_prefix():
    """Tab 切在短语中间、尾部列含英文+中文：英文片段归并回单词侧。"""
    entries, errors = parse_batch_text("for\texample, 例如")
    assert entries == [('for example', '例如')]
    assert errors == []


def test_tab_inside_phrase_various_shapes():
    """同类形态：make use of / take a photo / National Day。"""
    entries, _ = parse_batch_text(
        "make\tuse of, 使用\ntake\ta photo, 拍照\nNational\tDay, 国庆节")
    assert entries == [('make use of', '使用'),
                       ('take a photo', '拍照'),
                       ('National Day', '国庆节')]


def test_tab_before_paren_translation():
    """Tab 切在单词后、释义以 (= 同义词) 开头：括号段归并回单词侧。"""
    entries, _ = parse_batch_text("gym\t(= gymnasium), 体育馆")
    assert entries == [('gym (= gymnasium)', '体育馆')]


def test_comma_inside_parens_not_a_separator():
    """无 Tab 行：括号内的逗号是词条内部标点，不参与切分。"""
    entries, _ = parse_batch_text("kilo (= kilogram, kilogramme), 千克；公斤")
    assert entries == [('kilo (= kilogram, kilogramme)', '千克；公斤')]


def test_pos_token_in_mixed_column_stays_in_translation():
    """中文列开头是词性标注（n. 等）时不归并回单词侧。"""
    entries, _ = parse_batch_text("apple\tn. 苹果")
    assert entries == [('apple', 'n. 苹果')]


def test_paren_aware_separator_keeps_plain_lines_unchanged():
    """无括号 / 中文括号行不受括号感知逻辑影响。"""
    entries, _ = parse_batch_text("cat,猫\napple 苹果（一种水果）")
    assert entries == [('cat', '猫'), ('apple', '苹果（一种水果）')]


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
