# tests/test_html_generator.py
from src.html_generator import build_full_document, generate_day_page
from src.word_selector import DayPlan, WordEntry


def test_document_has_doctype_and_style():
    """完整文档以 <!DOCTYPE html> 开头，含 <style> 和 .focus-row，以 </html> 结尾。"""
    plan = DayPlan(1, [WordEntry('apple', '苹果', 'U1')], [WordEntry('cat', '猫', 'U3')])
    html = build_full_document([plan], total_count=2, focus_count=1, review_count=1)
    assert html.lstrip().startswith('<!DOCTYPE html>')
    assert '<style>' in html and '.focus-row' in html
    assert html.rstrip().endswith('</html>')


def test_day_page_contains_translation_not_word():
    """页面含释义，不含英文单词（word 单元格须空），含天数标题。"""
    plan = DayPlan(1, [WordEntry('apple', '苹果', 'U1')], [])
    page = generate_day_page(plan)
    assert '苹果' in page
    assert 'apple' not in page  # word 单元格必须为空
    assert '第1天' in page


def test_review_separator_present_when_both():
    """重点+复习同时存在时出现"复习单词"分隔行。"""
    plan = DayPlan(1, [WordEntry('apple', '苹果', 'U1')], [WordEntry('cat', '猫', 'U3')])
    page = generate_day_page(plan)
    assert '复习单词' in page


def test_no_separator_when_only_focus():
    """仅重点单词时不出现分隔行。"""
    plan = DayPlan(1, [WordEntry('apple', '苹果', 'U1')], [])
    page = generate_day_page(plan)
    assert '复习单词' not in page


def test_no_separator_when_only_review():
    """仅复习单词时也不出现分隔行。"""
    plan = DayPlan(1, [], [WordEntry('cat', '猫', 'U3')])
    page = generate_day_page(plan)
    assert '复习单词' not in page


def test_multiple_days_page_breaks():
    """2 页 → 恰 1 个外层显式分页符 div（非 CSS 里的）。"""
    plans = [
        DayPlan(1, [WordEntry('a', '甲', 'U1')], []),
        DayPlan(2, [WordEntry('b', '乙', 'U1')], [])
    ]
    html = build_full_document(plans, 1, 1, 0)
    # 搜索外层分页 div（不在 <style> 内）
    style_end = html.index('</style>')
    body_part = html[style_end:]
    assert '<div style="page-break-after: always;"></div>' in body_part


def test_on_progress_invoked_per_day():
    """3 页 → 回调序列 [(1,3),(2,3),(3,3)]。"""
    calls = []
    plan = DayPlan(1, [WordEntry('a', '甲', 'U1')], [])
    build_full_document([plan] * 3, 1, 1, 0, on_progress=lambda c, t: calls.append((c, t)))
    assert calls == [(1, 3), (2, 3), (3, 3)]


def test_date_section_present():
    """日期栏存在；学生姓名/签字/完成情况均已移除。"""
    plan = DayPlan(1, [WordEntry('a', '甲', 'U1')], [])
    page = generate_day_page(plan)
    assert '日期' in page
    assert '学生姓名' not in page
    assert '签字' not in page
    assert '完成情况' not in page


def test_no_score_column():
    """得分/总分已移除。"""
    plan = DayPlan(1, [WordEntry('a', '甲', 'U1')], [])
    page = generate_day_page(plan)
    assert '得分' not in page
    assert '总分' not in page
    assert 'score-cell' not in page


def test_correction_column_last():
    """更正列存在且在最后（单元之后），批改列已改名。"""
    plan = DayPlan(1, [WordEntry('a', '甲', 'U1')], [])
    page = generate_day_page(plan)
    assert '更正' in page
    assert '批改' not in page
    assert page.index('单元') < page.index('更正')  # 更正位于末列


def test_stats_row_shows_total():
    """统计行显示总单词数。"""
    plan = DayPlan(1, [WordEntry('a', '甲', 'U1')], [WordEntry('b', '乙', 'U2')])
    page = generate_day_page(plan)
    assert '2个单词' in page
