# src/data_loader.py
import json
import os
import sys


def get_data_file_path(filename):
    """获取数据文件路径"""
    if getattr(sys, 'frozen', False):
        # 打包环境
        base_path = sys._MEIPASS
        return os.path.join(base_path, 'src', filename)
    else:
        # 开发环境
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, filename)


def load_word_data(json_file=None):
    """加载单词数据"""
    if json_file is None:
        json_file = get_data_file_path('words.json')

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 直接从 word_list 获取所有单元
        units = [unit_info["unit"] for unit_info in data.get("word_list", [])]

        # 创建单元到单词的映射
        unit_words = {}
        for unit_info in data.get("word_list", []):
            unit_words[unit_info["unit"]] = unit_info["words"]

        return {
            'units': units,
            'unit_words': unit_words
        }
    except Exception as e:
        raise Exception(f"加载单词数据失败: {e}")


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
    """保存配置文件"""
    if config_file is None:
        # 打包环境保存到exe所在目录
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            config_file = os.path.join(exe_dir, 'config.json')
        else:
            # 开发环境
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_file = os.path.join(current_dir, 'config.json')

    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(config_file), exist_ok=True)

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存配置失败: {e}")
        return False
