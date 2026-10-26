# tests/test_data_loader.py
import json
import os
import pytest

from src.data_loader import load_word_data, save_word_data

SAMPLE = {"word_list": [{"unit": "U1", "words": [{"word": "a", "translation": "甲"}]}]}


def test_load_returns_word_list_and_aliases(tmp_path):
    """load_word_data 返回 word_list；unit_words 与 word_list 共享引用（alias）。"""
    f = tmp_path / "words.json"
    f.write_text(json.dumps(SAMPLE, ensure_ascii=False), encoding='utf-8')
    data = load_word_data(json_file=str(f))
    assert data['units'] == ['U1']
    assert data['word_list'] == SAMPLE['word_list']
    # alias 验证：unit_words[U1] IS word_list[0]['words']
    assert data['unit_words']['U1'] is data['word_list'][0]['words']


def test_save_round_trip(tmp_path):
    """save → load → 数据一致。"""
    f = tmp_path / "out.json"
    save_word_data(SAMPLE['word_list'], file=str(f))
    data = load_word_data(json_file=str(f))
    assert data['units'] == ['U1']
    assert data['unit_words']['U1'][0]['word'] == 'a'
    assert data['unit_words']['U1'][0]['translation'] == '甲'


def test_save_with_explicit_file(tmp_path):
    """save_word_data(file=...) 只写指定文件。"""
    f = tmp_path / "safe.json"
    save_word_data([], file=str(f))
    with open(str(f), 'r', encoding='utf-8') as fp:
        saved = json.load(fp)
    assert saved['word_list'] == []


def test_save_preserves_complex_data(tmp_path):
    """保存含多单元的数据后可正确加载。"""
    complex_data = [
        {"unit": "U1", "words": [{"word": "hello", "translation": "你好"}]},
        {"unit": "U2", "words": [
            {"word": "goodbye", "translation": "再见"},
            {"word": "right", "translation": "右边；正确的"}
        ]}
    ]
    f = tmp_path / "complex.json"
    save_word_data(complex_data, file=str(f))
    data = load_word_data(json_file=str(f))
    assert data['units'] == ['U1', 'U2']
    assert len(data['unit_words']['U2']) == 2
    assert data['unit_words']['U2'][1]['word'] == 'right'
