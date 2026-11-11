# main.py
import os
import sys

# 设置项目根目录到 Python 路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 检查是否是打包环境
if getattr(sys, 'frozen', False):
    # 打包环境：添加临时解压目录到路径
    sys.path.insert(0, sys._MEIPASS)

from PyQt6.QtWidgets import QApplication

from src.gui.main_window import WordDictationGUI

# 集中主题：全项目唯一的样式表。控件通过动态属性选择语义角色（role/status/accent），
# 颜色等视觉 Token 只在这里定义一次。
# 文字色与白/浅底对比度均 ≥ 4.5:1（WCAG AA）：
#   #2E7D32≈5.1:1  #1565C0≈5.8:1  #C62828≈5.6:1  #757575≈4.6:1
APP_STYLESHEET = """
QPushButton[role="primary"] {
    background-color: #2E7D32; color: white; font-weight: bold;
    padding: 8px 20px; border: 1px solid #2E7D32; border-radius: 4px;
}
QPushButton[role="info"] {
    background-color: #1565C0; color: white; font-weight: bold;
    padding: 8px 20px; border: 1px solid #1565C0; border-radius: 4px;
}
QPushButton[role="danger"] {
    background-color: #C62828; color: white; font-weight: bold;
    padding: 8px 20px; border: 1px solid #C62828; border-radius: 4px;
}
/* 键盘焦点：亮色描边（覆盖样式表默认吞掉的原生焦点框） */
QPushButton[role="primary"]:focus,
QPushButton[role="info"]:focus,
QPushButton[role="danger"]:focus {
    border: 2px solid #B3E5FC;
}
QLabel[status="success"] { color: #2E7D32; }
QLabel[status="danger"]  { color: #C62828; }
QLabel[status="muted"]   { color: #757575; }
QLabel[status="info"]    { color: #1565C0; }
/* 单元选择页两组的标题色区分：重点=橙，复习=蓝（仅染标题，不动原生边框） */
QGroupBox[accent="focus"]::title  { color: #E65100; }
QGroupBox[accent="review"]::title { color: #1565C0; }
"""


def main():
    """主函数"""
    # High-DPI：Qt6 默认始终启用缩放（原 Qt5 的 AA_EnableHighDpiScaling/AA_UseHighDpiPixmaps 已随枚举移除）

    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    window = WordDictationGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
