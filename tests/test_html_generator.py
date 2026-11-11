# tests/test_html_generator.py
import re

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
    """分页由 .page 的 CSS 规则驱动；<body> 内不得出现任何分页空 div
    （空 div 会在分页后再强制分页一次，打印出整页空白）。"""
    plans = [
        DayPlan(1, [WordEntry('a', '甲', 'U1')], []),
        DayPlan(2, [WordEntry('b', '乙', 'U1')], [])
    ]
    html = build_full_document(plans, 1, 1, 0)
    # 分页规则只应存在于 <style> 块内
    style_end = html.index('</style>')
    body_part = html[style_end:]
    assert 'page-break-after' not in body_part
    assert 'break-after' not in body_part
    # CSS 内同时写新旧两种分页属性，且末页不强制分页
    style_part = html[:style_end]
    assert 'page-break-after: always' in style_part
    assert 'break-after: page' in style_part
    assert re.search(r'\.page:last-child\s*\{[^}]*break-after:\s*auto', style_part)


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


# ── 答案页 ──────────────────────────────────────────────────────────────

def test_answer_page_appended_at_end():
    """文档末尾追加答案页：含"参考答案"标题与全部单词的英文+释义。"""
    plan = DayPlan(1, [WordEntry('apple', '苹果', 'U1')], [WordEntry('cat', '猫', 'U3')])
    html = build_full_document([plan], total_count=2, focus_count=1, review_count=1)
    answer = html[html.index('参考答案'):]
    assert 'apple' in answer and '苹果' in answer
    assert 'cat' in answer and '猫' in answer
    assert html.rstrip().endswith('</html>')  # 答案页位于 </html> 之前


def test_answer_page_grouped_by_day_in_question_order():
    """答案页按天分组：标题独立成行，组内条目保持题目页（重点→复习）顺序。"""
    plans = [
        DayPlan(1, [WordEntry('a', '甲', 'U1'), WordEntry('b', '乙', 'U2')],
                [WordEntry('c', '丙', 'U1')]),
        DayPlan(2, [WordEntry('d', '丁', 'U1')], []),
    ]
    html = build_full_document(plans, 3, 2, 1)
    answer = html[html.index('参考答案'):]
    assert answer.count('class="answer-day-head"') == 2
    assert answer.index('第1天') < answer.index('甲') < answer.index('乙') < \
        answer.index('丙') < answer.index('第2天') < answer.index('丁')


def test_answer_page_dedup_within_day_keeps_cross_day():
    """同一天内重复词（重点/复习共享）只记首次出现；跨天重复正常保留。"""
    plans = [
        DayPlan(1, [WordEntry('a', '甲', 'U1')], [WordEntry('a', '甲二', 'U1')]),
        DayPlan(2, [WordEntry('a', '甲', 'U1')], []),
    ]
    html = build_full_document(plans, 1, 1, 1)
    answer = html[html.index('参考答案'):]
    assert answer.count('class="answer-item"') == 2  # 第1天去重后 1 条 + 第2天 1 条
    assert '甲二' not in answer  # 只记当天首次出现的释义


def test_answer_page_numbering_restarts_per_day():
    """每天内编号从 1 连续，无跳号、无错位。"""
    plans = [
        DayPlan(1, [WordEntry('a', '甲', 'U1')], [WordEntry('b', '乙', 'U1')]),
        DayPlan(2, [WordEntry('c', '丙', 'U1')], []),
    ]
    html = build_full_document(plans, 2, 1, 1)
    answer = html[html.index('参考答案'):]
    nums = re.findall(r'class="answer-item">(\d+)\. ', answer)
    assert nums == ['1', '2', '1']


def test_answer_page_separator_between_word_and_translation():
    """英文与释义之间有明确分隔符 ' — '，不粘连。"""
    plan = DayPlan(1, [WordEntry('apple', '苹果', 'U1')], [])
    html = build_full_document([plan], 1, 1, 0)
    assert 'apple — 苹果' in html


def test_answer_page_compact_multicolumn_format():
    """答案页多列紧凑排版：column-count 两栏、条目防栏边界截断、无表格。"""
    plans = [
        DayPlan(1, [WordEntry('a', '甲', 'U1')], [WordEntry('b', '乙', 'U2')]),
        DayPlan(2, [WordEntry('c', '丙', 'U1')], []),
    ]
    html = build_full_document(plans, 2, 2, 0)
    answer = html[html.index('参考答案'):]
    assert 'column-count: 2' in html        # 两栏排布
    assert 'column-gap: 16px' in html       # 栏距 16px
    assert 'break-inside: avoid' in html    # 条目不被栏边界截断
    assert '<table' not in answer           # 不复用题目页表格
    assert 'separator-row' not in answer    # 无分组大标题表格行
    assert '#' not in answer                # 无 Markdown/结构标记泄漏


def test_day_page_row_count_equals_words():
    """答题区行数等于当天单词数（重点+复习）；分隔行/统计行不计入。"""
    plan = DayPlan(1, [WordEntry('a', '甲', 'U1'), WordEntry('b', '乙', 'U2')],
                   [WordEntry('c', '丙', 'U3')])
    page = generate_day_page(plan)
    assert page.count('class="focus-row"') + page.count('class="review-row"') == 3


def test_answer_page_no_blanks_or_correction():
    """答案页只列答案：无更正列、无作答空白、无日期栏。"""
    plan = DayPlan(1, [WordEntry('apple', '苹果', 'U1')], [])
    html = build_full_document([plan], 1, 1, 0)
    answer = html[html.index('参考答案'):]
    assert '更正' not in answer
    assert 'correction-cell' not in answer
    assert '日期' not in answer


def test_no_answer_page_when_no_words():
    """无单词时不生成答案页（空文档沿用原行为）。"""
    html = build_full_document([], 0, 0, 0)
    assert '参考答案' not in html
    empty_day = build_full_document([DayPlan(1, [], [])], 0, 0, 0)
    assert '参考答案' not in empty_day


def test_answer_page_is_last_page_div():
    """答案页复用 .page 分页机制，且是最后一个 .page 容器、位于全部日页之后。"""
    plans = [
        DayPlan(1, [WordEntry('a', '甲', 'U1')], []),
        DayPlan(2, [WordEntry('b', '乙', 'U1')], []),
    ]
    html = build_full_document(plans, 1, 1, 0)
    answer_pos = html.index('<div class="page answer-page">')
    assert '<div class="page' not in html[answer_pos + 1:]  # 其后无其他 .page
    assert '第1天' in html[:answer_pos] and '第2天' in html[:answer_pos]
