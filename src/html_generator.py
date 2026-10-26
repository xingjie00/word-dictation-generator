# src/html_generator.py
"""HTML 文档生成：CSS/HTML 模板常量 + 听写文档构建。"""
from typing import List, Optional, Callable

from src.word_selector import DayPlan, WordEntry


# ── CSS 样式（从 main_window.py 原样搬移） ──────────────────────────────

_CSS = """\
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
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
                page-break-after: always;
                height: 100vh;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            }
            .page:last-child {
                page-break-after: auto;
            }
        }
        .page {
            padding: 20mm;
            min-height: 297mm; /* A4纸高度 */
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
        .correction-cell, .score-cell {
            background-color: #f5f5f5;
        }
        .stats-row {
            background-color: #e8f4ff;
            font-weight: bold;
        }
        .total-label, .total-value, .total-score {
            text-align: center;
            font-size: 13px;
        }
        .signature-section {
            margin-top: 30px;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
        }
        .signature-left, .signature-right {
            flex: 1;
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
    """渲染一天的听写页面（<div class="page"> 含表格 + 签名栏）。

    Args:
        plan: 该天的 DayPlan（含 focus_words / review_words）。

    Returns:
        HTML 字符串片段。
    """
    total_words = len(plan.focus_words) + len(plan.review_words)

    html = f"""
        <div class="page">
            <div class="header">
                <h1>英语单词听写练习 第{plan.day_num}天</h1>
            </div>

            <table>
                <thead>
                    <tr>
                        <th width="10%">序号</th>
                        <th width="25%">英文单词</th>
                        <th width="25%">中文释义</th>
                        <th width="10%">批改</th>
                        <th width="20%">单元</th>
                        <th width="10%">得分</th>
                    </tr>
                </thead>
                <tbody>
    """

    # 重点单词行
    row_num = 1
    for i, item in enumerate(plan.focus_words, 1):
        html += f"""
                    <tr class="focus-row">
                        <td>{i}</td>
                        <td class="word-cell">

                        </td>
                        <td>{item.translation}</td>
                        <td class="correction-cell"></td>
                        <td>{item.unit}</td>
                        <td class="score-cell"></td>
                    </tr>
        """
        row_num = i + 1

    # 复习单词行
    if plan.review_words:
        if plan.focus_words:
            html += """
                    <tr class="separator-row">
                        <td colspan="6" class="section-title">复习单词</td>
                    </tr>
            """
        for i, item in enumerate(plan.review_words, row_num):
            html += f"""
                    <tr class="review-row">
                        <td>{i}</td>
                        <td class="word-cell">

                        </td>
                        <td>{item.translation}</td>
                        <td class="correction-cell"></td>
                        <td>{item.unit}</td>
                        <td class="score-cell"></td>
                    </tr>
            """

    # 统计行 + 签名栏
    html += f"""
                    <tr class="stats-row">
                        <td colspan="2" class="total-label">今日总计</td>
                        <td colspan="2" class="total-value">{total_words}个单词</td>
                        <td colspan="2" class="total-score">总分: ______</td>
                    </tr>
                </tbody>
            </table>

            <div class="signature-section">
                <div class="signature-left">
                    <div>学生姓名: _______________</div>
                    <div>家长/老师签字: _______________</div>
                </div>
                <div class="signature-right">
                    <div>批改日期: _______________</div>
                    <div>完成情况: □优秀 □良好 □一般 □需改进</div>
                </div>
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
        完整 HTML 文档字符串。
    """
    days = len(day_plans)
    css_indented = "\n".join("    " + line if line.strip() else line for line in _CSS.split("\n"))
    html = _HTML_HEAD_TEMPLATE.format(days=days, css=css_indented)

    for i, plan in enumerate(day_plans):
        html += generate_day_page(plan)
        if i < days - 1:
            html += '<div style="page-break-after: always;"></div>'
        if on_progress:
            on_progress(i + 1, days)

    html += _HTML_TAIL
    return html
