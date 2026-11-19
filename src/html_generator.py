# src/html_generator.py
"""HTML 文档生成：CSS/HTML 模板常量 + 听写文档构建。"""
from typing import List, Optional, Callable, Set

from src.word_selector import DayPlan, WordEntry


# ── CSS 样式（从 main_window.py 原样搬移） ──────────────────────────────

_CSS = """\
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        @page {
            size: A4;
            margin: 0;
        }
        body {
            font-family: 'Microsoft YaHei', 'SimHei', Arial, sans-serif;
            font-size: 14px;
            line-height: 1.4;
            color: #333;
            background: #fff;
        }
        @media print {
            .page {
                /* 打印时高度自适应：固定 297mm 会在行数超限时把统计行/签名区
                   叠印到表格上；改为 auto 交给浏览器按内容自然分页。每天一个
                   .page，续页表头由 <thead> 自动重复，行不被截断（见下方 tr
                   的 break-inside 规则）。顶对齐，不再上下撑开 */
                min-height: 0;
                height: auto;
                box-sizing: border-box;
                page-break-after: always;
                break-after: page;
                display: flex;
                flex-direction: column;
                justify-content: flex-start;
            }
            .page:last-child {
                page-break-after: auto;
                break-after: auto;
            }
        }
        .page {
            padding: 20mm;
            min-height: 297mm; /* A4纸高度（仅屏幕预览；打印时上方 @media print 规则覆盖） */
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
        }
        .header {
            text-align: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #0066cc;
        }
        .header h1 {
            font-size: 24px;
            font-weight: bold;
            color: #0066cc;
            margin: 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            table-layout: fixed;
        }
        th, td {
            border: 1px solid #666;
            padding: 8px 5px;
            text-align: center;
            vertical-align: middle;
            word-wrap: break-word;
        }
        tr {
            /* 打印分页由浏览器自然进行：行内绝不截断（跨页只能整行下移） */
            page-break-inside: avoid;
            break-inside: avoid;
        }
        th {
            background-color: #f0f8ff;
            font-weight: bold;
            font-size: 13px;
        }
        .focus-row {
            background-color: #f9f9f9;
        }
        .review-row {
            background-color: #fff;
        }
        .separator-row {
            background-color: #e6f3ff;
        }
        .section-title {
            font-weight: bold;
            font-style: italic;
            text-align: center;
            font-size: 14px;
            color: #0066cc;
        }
        .word-cell {
            text-align: left;
            padding-left: 10px;
        }
        .underline-space {
            border-bottom: 1px solid #999;
            min-height: 20px;
            display: flex;
            align-items: center;
        }
        .correction-cell {
            background-color: #f5f5f5;
        }
        .stats-row {
            background-color: #e8f4ff;
            font-weight: bold;
        }
        .total-label, .total-value {
            text-align: center;
            font-size: 13px;
        }
        .signature-section {
            /* 日期/签名栏位于标题正下方（表格之后会被分页挤成孤行） */
            margin-top: 0;
            display: flex;
            justify-content: flex-end;
            align-items: flex-end;
        }
        .signature-right {
            text-align: right;
        }
        .signature-section div {
            margin-bottom: 8px;
            font-size: 13px;
        }
        .no-print {
            display: none;
        }
        .answer-page {
            justify-content: flex-start;
        }
        .answer-list {
            font-size: 13px;
            column-count: 2;
            column-gap: 16px;
        }
        .answer-item {
            margin: 0 0 2px;
            break-inside: avoid;
        }
        .answer-day-head {
            font-weight: bold;
            color: #0066cc;
            margin: 6px 0 2px;
            break-after: avoid;
        }
        @media screen {
            body {
                background-color: #f5f5f5;
            }
            .page {
                background: white;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                margin: 20px auto;
                max-width: 210mm;
            }
        }\
"""

_HTML_HEAD_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>英语单词听写练习 - {days}天</title>
    <style>
{css}
    </style>
</head>
<body>
"""

_HTML_TAIL = """
</body>
</html>
"""


# ── 单页渲染 ────────────────────────────────────────────────────────────

def generate_day_page(plan: DayPlan) -> str:
    """渲染一天的听写页面（单个 .page；打印分页完全交由浏览器自然进行）。

    不做任何截断也不做程序内分块：重点词与复习词拼接成有序列表后全部
    渲染进同一个 .page。打印时浏览器按物理页高自然断页——<thead> 在
    续页自动重复表头，行级 break-inside: avoid 保证任何一行不被从中间
    截断，序号跨页连续。

    - 标题“第N天”；“复习单词”分隔行插在全局第一条复习词之前；
    - “今日总计”统计行在表尾；
    - 日期/签名栏固定在标题正下方：若放在表格之后，表格恰好填满页面时
      会被挤成孤行页（历史缺陷），放在顶部则不受分页影响。

    Args:
        plan: 该天的 DayPlan（含 focus_words / review_words）。

    Returns:
        HTML 字符串片段（一个 <div class="page">）。
    """
    total_words = len(plan.focus_words) + len(plan.review_words)
    first_review_idx = len(plan.focus_words)  # 第一条复习词的全局下标

    rows = ""
    for global_idx, item in enumerate(list(plan.focus_words)
                                      + list(plan.review_words)):
        is_review = global_idx >= first_review_idx
        row_num = global_idx + 1  # 序号跨页连续，不重置

        # 分隔行：仅插在全局第一条复习词之前
        if is_review and plan.focus_words and global_idx == first_review_idx:
            rows += """
                    <tr class="separator-row">
                        <td colspan="5" class="section-title">复习单词</td>
                    </tr>
            """

        row_class = "review-row" if is_review else "focus-row"
        rows += f"""
                <tr class="{row_class}">
                    <td>{row_num}</td>
                    <td class="word-cell">

                    </td>
                    <td>{item.translation}</td>
                    <td>{item.unit}</td>
                    <td class="correction-cell"></td>
                </tr>
        """

    # 断言校验：渲染行数必须等于当天实际单词数，不一致时报错而非静默生成
    rendered_rows = (rows.count('class="focus-row"')
                     + rows.count('class="review-row"'))
    assert rendered_rows == total_words, (
        f"答题行数({rendered_rows})与当天单词数({total_words})不一致，"
        f"第{plan.day_num}天生成异常"
    )

    page = f"""
        <div class="page">
            <div class="header">
                <h1>英语单词听写练习 第{plan.day_num}天</h1>
            </div>

            <div class="signature-section">
                <div class="signature-right">
                    <div>日期: _______________</div>
                </div>
            </div>

            <table>
                <thead>
                    <tr>
                        <th width="5%">序号</th>
                        <th width="30%">英文单词</th>
                        <th width="25%">中文释义</th>
                        <th width="20%">单元</th>
                        <th width="20%">更正</th>
                    </tr>
                </thead>
                <tbody>
    """
    if total_words:
        page += rows
        page += f"""
                    <tr class="stats-row">
                        <td colspan="2" class="total-label">今日总计</td>
                        <td colspan="3" class="total-value">{total_words}个单词</td>
                    </tr>
    """
    page += """
                </tbody>
            </table>
        </div>
    """
    return page


def generate_answer_page(day_plans: List[DayPlan]) -> str:
    """渲染答案页（<div class="page answer-page">）：按天分组的多列紧凑
    列表，列出全部单词的英文与释义。

    数据与顺序：直接遍历传入的 day_plans（与题目页同一份数据，不重查），
    每天按题目顺序（重点 → 复习）取词；同一天内按英文单词去重（共享词
    既作重点又作复习时只记首次出现的释义），跨天重复正常保留。每天内
    从 1 重新连续编号。

    视觉格式（紧凑多列）：
    - 条目 13px（≈10pt，小于题目页正文 14px），行距沿用全局 1.4，条目
      间距 2px；两栏排布（column-count: 2，栏距 16px），break-inside:
      avoid 防止条目被栏边界截断；
    - 每天标题（第N天）独立成行，加粗蓝色小字，break-after: avoid 避免
      标题孤悬栏/页尾。

    Args:
        day_plans: 各天的 DayPlan 列表（与题目页共用同一份数据）。

    Returns:
        HTML 字符串片段。
    """
    html = """
        <div class="page answer-page">
            <div class="header">
                <h1>参考答案</h1>
            </div>

            <div class="answer-list">
    """

    for plan in day_plans:
        # 当天单词按题目顺序收集；同一天内去重（共享词只记首次出现）
        day_words: List[WordEntry] = []
        seen: Set[str] = set()
        for item in plan.focus_words + plan.review_words:
            if item.word not in seen:
                seen.add(item.word)
                day_words.append(item)
        if not day_words:  # 防御：空天不渲染空分组
            continue
        html += f"""
                    <p class="answer-day-head">第{plan.day_num}天</p>
        """
        for i, item in enumerate(day_words, 1):
            html += f"""
                    <p class="answer-item">{i}. {item.word} — {item.translation}</p>
            """

    html += """
            </div>
        </div>
    """

    return html


# ── 完整文档构建 ────────────────────────────────────────────────────────

def build_full_document(
    day_plans: List[DayPlan],
    total_count: int,
    focus_count: int,
    review_count: int,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> str:
    """构建完整的 HTML 听写文档。

    Args:
        day_plans: 各天的 DayPlan 列表。
        total_count: 每天总单词数（用于信息展示）。
        focus_count: 每天重点单词数。
        review_count: 每天复习单词数。
        on_progress: 进度回调 (current_day, total_days)。

    Returns:
        完整 HTML 文档字符串（末尾含参考答案页；无单词时不含）。
    """
    days = len(day_plans)
    css_indented = "\n".join("    " + line if line.strip() else line for line in _CSS.split("\n"))
    html = _HTML_HEAD_TEMPLATE.format(days=days, css=css_indented)

    for i, plan in enumerate(day_plans):
        html += generate_day_page(plan)
        # 天与天之间不加任何空分页 div：.page 自身的 page-break-after 规则
        # 已驱动分页，额外空 div 会在分页后再强制分页一次，产生整页空白
        if on_progress:
            on_progress(i + 1, days)

    # 文末追加参考答案页（复用 .page 分页机制；无单词时省略）
    if any(plan.focus_words or plan.review_words for plan in day_plans):
        html += generate_answer_page(day_plans)

    html += _HTML_TAIL
    return html
