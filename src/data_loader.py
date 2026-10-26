# src/data_loader.py
"""路径工具与配置读写。单词数据已迁移至 src/db.py（SQLite）。"""
import json
import os
import sys


def find_project_root():
    """向上查找包含resources目录的项目根目录"""
    current = os.path.dirname(os.path.abspath(__file__))

    # 向上查找最多5层
    for _ in range(5):
        # 检查当前目录是否有resources目录
        resources_dir = os.path.join(current, 'resources')
        if os.path.exists(resources_dir):
            return current

        # 检查上一级
        parent = os.path.dirname(current)
        if parent == current:  # 到达根目录
            break
        current = parent

    # 如果没找到，返回当前文件所在目录的上一级
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_data_file_path(filename):
    """获取数据文件路径（优先外部，不存在则用内部）"""
    # 优先级1：exe所在目录的resources文件夹（用户可修改）
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        external_path = os.path.join(exe_dir, 'resources', filename)

        # 如果外部文件存在，直接使用
        if os.path.exists(external_path):
            # print(f"✅ 使用外部文件: {external_path}")
            return external_path

        # 外部文件不存在，检查内部资源
        if hasattr(sys, '_MEIPASS'):
            # 单文件模式：资源在临时目录
            internal_path = os.path.join(sys._MEIPASS, 'resources', filename)
            if os.path.exists(internal_path):
                # print(f"⚠️ 外部文件不存在，使用内部: {internal_path}")
                return internal_path
        else:
            # 文件夹模式
            internal_path = os.path.join(exe_dir, '_internal', 'resources', filename)
            if os.path.exists(internal_path):
                # print(f"⚠️ 外部文件不存在，使用内部: {internal_path}")
                return internal_path

    # 开发环境或非打包环境
    project_root = find_project_root()
    dev_path = os.path.join(project_root, 'resources', filename)
    return dev_path


def load_config(config_file=None):
    """加载配置文件"""
    if config_file is None:
        config_file = get_data_file_path('config.json')

    default_config = {
        'focus_count': 10,
        'total_count': 18,
        'days': 5,
        'filename': '单词听写'
    }

    try:
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 确保所有配置项都存在
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            return default_config
    except Exception:
        return default_config


def save_config(config, config_file=None):
    """保存配置文件（总是保存到外部）"""
    if config_file is None:
        # 总是保存到exe所在目录的resources文件夹
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            config_file = os.path.join(exe_dir, 'resources', 'config.json')
        else:
            # 开发环境
            config_file = get_data_file_path('config.json')

    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(config_file), exist_ok=True)

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存配置失败: {e}")
        return False


def get_resource_folder():
    """获取资源文件夹路径"""
    if getattr(sys, 'frozen', False):
        # 打包环境：返回exe所在目录的resources文件夹
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, 'resources')
    else:
        # 开发环境
        project_root = find_project_root()
        return os.path.join(project_root, 'resources')
