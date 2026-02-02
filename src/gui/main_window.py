# src/gui/main_window.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import random
import datetime

from src.data_loader import load_word_data, load_config, save_config
from src.gui.tabs.unit_selection import UnitSelectionTab
from src.gui.tabs.settings import SettingsTab


class WordDictationGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("单词听写生成器 v2.0")
        self.root.geometry("700x600")

        # 窗口关闭时保存配置
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 加载配置
        self.config = load_config()

        # 加载数据
        try:
            self.data = load_word_data()
            self.units = self.data['units']
        except Exception as e:
            messagebox.showerror("错误", f"加载单词数据失败: {e}")
            self.root.destroy()
            return

        self.setup_ui()

    def setup_ui(self):
        """设置用户界面"""
        # 标题
        title_label = tk.Label(self.root, text="单词听写生成器 v2.0",
                               font=("Microsoft YaHei", 16, "bold"))
        title_label.pack(pady=10)

        # 创建Notebook（标签页）
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # 初始化标签页
        self.unit_tab = UnitSelectionTab(self.notebook, self.units)
        self.settings_tab = SettingsTab(self.notebook, self.config)

        # 添加标签页
        self.notebook.add(self.unit_tab.frame, text="选择单元")
        self.notebook.add(self.settings_tab.frame, text="设置参数")

        # 生成按钮
        generate_btn = tk.Button(self.root, text="生成HTML听写文档",
                                 command=self.generate_document,
                                 bg="#4CAF50", fg="white",
                                 font=("Microsoft YaHei", 12, "bold"),
                                 padx=20, pady=10)
        generate_btn.pack(pady=10)

        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = tk.Label(self.root, textvariable=self.status_var,
                              bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def save_current_config(self):
        """保存当前配置到文件"""
        config = {
            'focus_count': int(self.settings_tab.focus_count_var.get()),
            'total_count': int(self.settings_tab.total_count_var.get()),
            'days': int(self.settings_tab.days_var.get()),
            'filename': self.settings_tab.filename_var.get()
        }
        save_config(config)

    def on_closing(self):
        """窗口关闭时保存配置"""
        self.save_current_config()
        self.root.destroy()

    def generate_html_table_content(self, day_num, focus_units, review_units, focus_count, review_count):
        """生成一天的HTML表格内容"""
        # 选择单词
        focus_words = []
        review_words = []

        # 选择重点单词
        if focus_units:
            all_focus_words = []
            for unit in focus_units:
                words = self.data['unit_words'].get(unit, [])
                for word in words:
                    word_with_unit = word.copy()
                    word_with_unit["unit"] = unit
                    all_focus_words.append(word_with_unit)

            if all_focus_words:
                focus_count = min(focus_count, len(all_focus_words))
                focus_words = random.sample(all_focus_words, focus_count)

        # 选择复习单词
        if review_units:
            all_review_words = []
            for unit in review_units:
                words = self.data['unit_words'].get(unit, [])
                for word in words:
                    word_with_unit = word.copy()
                    word_with_unit["unit"] = unit
                    all_review_words.append(word_with_unit)

            if all_review_words:
                review_count = min(review_count, len(all_review_words))
                review_words = random.sample(all_review_words, review_count)

        # 生成表格HTML
        table_html = f"""
        <div class="page">
            <div class="header">
                <h1>英语单词听写练习 第{day_num}天</h1>
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

        # 添加重点单词
        row_num = 1
        if focus_words:
            for i, item in enumerate(focus_words, 1):
                table_html += f"""
                    <tr class="focus-row">
                        <td>{i}</td>
                        <td class="word-cell">
                   
                        </td>
                        <td>{item["translation"]}</td>
                        <td class="correction-cell"></td>
                        <td>{item["unit"]}</td>
                        <td class="score-cell"></td>
                    </tr>
                """
                row_num = i + 1

        # 添加复习单词（如果有重点和复习单词，添加分隔标记）
        if review_words:
            if focus_words:
                table_html += f"""
                    <tr class="separator-row">
                        <td colspan="6" class="section-title">复习单词</td>
                    </tr>
                """

            for i, item in enumerate(review_words, row_num):
                table_html += f"""
                    <tr class="review-row">
                        <td>{i}</td>
                        <td class="word-cell">
                        
                        </td>
                        <td>{item["translation"]}</td>
                        <td class="correction-cell"></td>
                        <td>{item["unit"]}</td>
                        <td class="score-cell"></td>
                    </tr>
                """

        total_words = len(focus_words) + len(review_words)

        # 添加统计信息和签名行
        table_html += f"""
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

        return table_html

    def generate_document(self):
        """生成HTML文档"""
        # 验证并获取参数
        self.settings_tab.update_word_counts()
        self.settings_tab.update_days()

        # 保存当前配置
        self.save_current_config()

        focus_unit = self.unit_tab.focus_var.get()
        if focus_unit == "无":
            focus_units = []
        else:
            focus_units = [focus_unit]

        # 获取选择的复习单元
        review_indices = self.unit_tab.review_listbox.curselection()
        review_units = [self.unit_tab.review_listbox.get(i) for i in review_indices]

        # 排除重点单元（如果选择了）
        if focus_units:
            review_units = [unit for unit in review_units if unit != focus_units[0]]

        # 检查参数
        if not review_units:
            messagebox.showwarning("警告", "请至少选择一个复习单元！")
            return

        try:
            focus_count = int(self.settings_tab.focus_count_var.get())
            total_count = int(self.settings_tab.total_count_var.get())
            days = int(self.settings_tab.days_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字！")
            return

        if focus_count < 0 or focus_count > total_count:
            messagebox.showerror("错误", f"重点单词数量必须在0-{total_count}之间！")
            return

        review_count = total_count - focus_count

        # 检查单词数量是否足够
        if focus_units:
            total_focus_words = sum(len(self.data['unit_words'].get(unit, []))
                                    for unit in focus_units)
            if total_focus_words < focus_count:
                messagebox.showwarning("警告",
                                       f"重点单元只有{total_focus_words}个单词，少于设定的{focus_count}个！")
                return

        total_review_words = sum(len(self.data['unit_words'].get(unit, []))
                                 for unit in review_units)
        if total_review_words < review_count:
            messagebox.showwarning("警告",
                                   f"复习单元总共只有{total_review_words}个单词，少于设定的{review_count}个！")
            return

        # 更新状态
        self.status_var.set("正在生成HTML文档...")
        self.root.update()

        try:
            # 生成完整的HTML文档
            html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>英语单词听写练习 - {days}天</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Microsoft YaHei', 'SimHei', Arial, sans-serif;
            font-size: 14px;
            line-height: 1.4;
            color: #333;
            background: #fff;
        }}
        @media print {{
            .page {{
                page-break-after: always;
                height: 100vh;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            }}
            .page:last-child {{
                page-break-after: auto;
            }}
        }}
        .page {{
            padding: 20mm;
            min-height: 297mm; /* A4纸高度 */
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .header {{
            text-align: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #0066cc;
        }}
        .header h1 {{
            font-size: 24px;
            font-weight: bold;
            color: #0066cc;
            margin: 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            table-layout: fixed;
        }}
        th, td {{
            border: 1px solid #666;
            padding: 8px 5px;
            text-align: center;
            vertical-align: middle;
            word-wrap: break-word;
        }}
        th {{
            background-color: #f0f8ff;
            font-weight: bold;
            font-size: 13px;
        }}
        .focus-row {{
            background-color: #f9f9f9;
        }}
        .review-row {{
            background-color: #fff;
        }}
        .separator-row {{
            background-color: #e6f3ff;
        }}
        .section-title {{
            font-weight: bold;
            font-style: italic;
            text-align: center;
            font-size: 14px;
            color: #0066cc;
        }}
        .word-cell {{
            text-align: left;
            padding-left: 10px;
        }}
        .underline-space {{
            border-bottom: 1px solid #999;
            min-height: 20px;
            display: flex;
            align-items: center;
        }}
        .correction-cell, .score-cell {{
            background-color: #f5f5f5;
        }}
        .stats-row {{
            background-color: #e8f4ff;
            font-weight: bold;
        }}
        .total-label, .total-value, .total-score {{
            text-align: center;
            font-size: 13px;
        }}
        .signature-section {{
            margin-top: 30px;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
        }}
        .signature-left, .signature-right {{
            flex: 1;
        }}
        .signature-right {{
            text-align: right;
        }}
        .signature-section div {{
            margin-bottom: 8px;
            font-size: 13px;
        }}
        .no-print {{
            display: none;
        }}
        @media screen {{
            body {{
                background-color: #f5f5f5;
            }}
            .page {{
                background: white;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                margin: 20px auto;
                max-width: 210mm;
            }}
        }}
    </style>
</head>
<body>
"""

            # 生成每一天的听写页
            for day in range(1, days + 1):
                table_content = self.generate_html_table_content(day, focus_units, review_units,
                                                                 focus_count, review_count)
                html_doc += table_content

                # 只在非最后一天添加分页符
                if day < days:
                    html_doc += '<div style="page-break-after: always;"></div>'

            html_doc += """
</body>
</html>
"""

            # 保存文档
            filename = f"{self.settings_tab.filename_var.get()}{days}天.html"
            filepath = filedialog.asksaveasfilename(
                defaultextension=".html",
                initialfile=filename,
                filetypes=[("HTML文档", "*.html"), ("所有文件", "*.*")]
            )

            if filepath:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(html_doc)

                self.status_var.set(f"HTML文档已保存: {os.path.basename(filepath)}")

                # 显示成功消息
                messagebox.showinfo("成功",
                                    f"HTML听写文档生成成功！\n\n"
                                    f"文件: {os.path.basename(filepath)}\n"
                                    f"天数: {days}天\n"
                                    f"总单词数: {total_count}个/天\n"
                                    f"重点单元: {focus_units[0] if focus_units else '无'}\n"
                                    f"复习单元: {len(review_units)}个\n"
                                    f"每天: {focus_count}个重点单词 + {review_count}个复习单词\n\n"
                                    f"提示：\n"
                                    f"• 可以用浏览器打开查看\n"
                                    f"• 推荐使用Ctrl+P打印\n"
                                    f"• 打印设置选择A4纸张")
            else:
                self.status_var.set("用户取消了保存")

        except Exception as e:
            self.status_var.set("生成失败")
            messagebox.showerror("错误", f"生成HTML文档时出错: {str(e)}")

    def run(self):
        """运行GUI"""
        self.root.mainloop()
