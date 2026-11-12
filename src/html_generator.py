# src/html_generator.py
"""HTML 文档生成：CSS/HTML 模板常量 + 听写文档构建。"""
from typing import List, Optional, Callable, Set

from src.word_selector import DayPlan, WordEntry


# 每页（.page）最大答题行数：固定容量，确保表头、统计行与签名区绝不被
# 挤出页面造成重叠。某天总词数超过此值时自动拆分为多个页面。
MAX_ROWS_PER_PAGE = 20


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
                   叠印到表格上；改为 auto 交给浏览器按内容自然分页，行数上限
                   由 MAX_ROWS_PER_PAGE 从数据层严格控制。顶对齐，不再上下撑开 */
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
            justify-content: space-between;
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
            margin-top: 30px;
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
    """渲染一天的听写页面（词数超过 MAX_ROWS_PER_PAGE 时含多个 .page）。

    不做任何截断：重点词与复习词拼接成有序列表后按 MAX_ROWS_PER_PAGE
    切块，每块渲染为一个完整页面。

    - 首页标题“第N天”，后续页标题“第N天（续）”，每页均含表头 <thead>；
    - 序号跨页连续（重点词接复习词，不重置）；
    - “复习单词”分隔行只在包含第一条复习词的页出现，且紧邻该行之前；
    - “今日总计”统计行与签名栏只在最后一页出现。

    Args:
        plan: 该天的 DayPlan（含 focus_words / review_words）。

    Returns:
        HTML 字符串片段（可能含多个 <div class="page">）。
    """
    total_words = len(plan.focus_words) + len(plan.review_words)
    # 重点 + 复习拼接成有序列表：序号天然连续（重点在前、复习在后），统一切块
    all_words = list(plan.focus_words) + list(plan.review_words)

    # 按 MAX_ROWS_PER_PAGE 切片；无词时保留单页结构（与原行为一致）
    chunks = [all_words[i:i + MAX_ROWS_PER_PAGE]
              for i in range(0, len(all_words), MAX_ROWS_PER_PAGE)] or [[]]

    first_review_idx = len(plan.focus_words)  # 第一条复习词的全局下标

    html = ""
    rendered_rows = 0
    for chunk_idx, chunk in enumerate(chunks):
        is_last_page = chunk_idx == len(chunks) - 1
        page_title = (f"第{plan.day_num}天" if chunk_idx == 0
                      else f"第{plan.day_num}天（续）")
        start = chunk_idx * MAX_ROWS_PER_PAGE  # 本页首行的全局下标

        page = f"""
        <div class="page">
            <div class="header">
                <h1>英语单词听写练习 {page_title}</h1>
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

        for offset, item in enumerate(chunk):
            global_idx = start + offset
            is_review = global_idx >= first_review_idx
            row_num = global_idx + 1  # 序号跨页连续，不重置

            # 分隔行：仅插在本页内第一条复习词（即全局第一条复习词）之前
            if is_review and plan.focus_words and global_idx == first_review_idx:
                page += """
                    <tr class="separator-row">
                        <td colspan="5" class="section-title">复习单词</td>
                    </tr>
            """

            row_class = "review-row" if is_review else "focus-row"
            page += f"""
                    <tr class="{row_class}">
                        <td>{row_num}</td>
                        <td class="word-cell">

                        </td>
                        <td>{item.translation}</td>
                        <td>{item.unit}</td>
                        <td class="correction-cell"></td>
                    </tr>
            """

        # 统计行 + 签名栏：仅最后一页；其余页直接收尾表格
        if is_last_page:
            page += f"""
                    <tr class="stats-row">
                        <td colspan="2" class="total-label">今日总计</td>
                        <td colspan="3" class="total-value">{total_words}个单词</td>
                    </tr>
                </tbody>
            </table>

            <div class="signature-section">
                <div class="signature-right">
                    <div>日期: _______________</div>
                </div>
            </div>
        </div>
    """
        else:
            page += """
                </tbody>
            </table>
        </div>
    """

        # 各块渲染行数累加，供末尾与当天单词总数核对
        rendered_rows += (page.count('class="focus-row"')
                          + page.count('class="review-row"'))
        html += page

    # 断言校验：各块渲染行数之和必须等于当天实际单词数，不一致时报错而非静默生成
    assert rendered_rows == total_words, (
        f"答题行数({rendered_rows})与当天单词数({total_words})不一致，"
        f"第{plan.day_num}天生成异常"
    )

    return html


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
