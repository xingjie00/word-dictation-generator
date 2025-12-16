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

from src.gui.main_window import WordDictationGUI


def main():
    """主函数"""
    app = WordDictationGUI()
    if hasattr(app, 'root'):
        app.run()


if __name__ == "__main__":
    main()
