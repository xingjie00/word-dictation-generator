# src/data_loader.py
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
    """获取数据文件路径"""
    if getattr(sys, 'frozen', False):
        # 打包环境
        base_path = sys._MEIPASS
        return os.path.join(base_path, 'resources', filename)
    else:
        # 开发环境
        project_root = find_project_root()
        result = os.path.join(project_root, 'resources', filename)

        # # 调试信息
        # print(f"🔍 get_data_file_path('{filename}')")
        # print(f"   项目根目录: {project_root}")
        # print(f"   最终路径: {result}")
        # print(f"   文件存在: {os.path.exists(result)}")

        return result


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
        # 统一使用 get_data_file_path 获取路径
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


# 调试函数
# def debug_project_structure():
#     """调试项目结构"""
#     print("=== 项目结构调试 ===")
#
#     # 查找项目根目录
#     project_root = find_project_root()
#     print(f"找到的项目根目录: {project_root}")
#
#     # 检查目录结构
#     print(f"\n📁 项目根目录内容:")
#     if os.path.exists(project_root):
#         for item in os.listdir(project_root):
#             item_path = os.path.join(project_root, item)
#             if os.path.isdir(item_path):
#                 print(f"  📂 {item}/")
#             else:
#                 print(f"  📄 {item}")
#
#     # 检查resources目录
#     resources_path = os.path.join(project_root, 'resources')
#     print(f"\n📁 resources 目录: {resources_path}")
#     print(f"   目录存在: {os.path.exists(resources_path)}")
#     if os.path.exists(resources_path):
#         print(f"   目录内容:")
#         for item in os.listdir(resources_path):
#             print(f"    - {item}")


# 如果直接运行此文件，执行调试
# if __name__ == "__main__":
#     debug_project_structure()
#
#     print("\n=== 测试路径函数 ===")
#     # 测试各种文件
#     test_files = ['words.json', 'config.json', 'main.py']
#     for filename in test_files:
#         try:
#             path = get_data_file_path(filename)
#             print(f"\n📁 {filename}:")
#             print(f"   路径: {path}")
#             print(f"   存在: {os.path.exists(path)}")
#         except Exception as e:
#             print(f"\n❌ {filename}: {e}")
#
#     print("\n=== 测试加载功能 ===")
#
#     # 测试加载数据
#     try:
#         word_data = load_word_data()
#         print(f"✅ 加载单词数据成功，共 {len(word_data['units'])} 个单元")
#     except Exception as e:
#         print(f"❌ 加载单词数据失败: {e}")
#
#     # 测试加载配置
#     config = load_config()
#     print(f"✅ 加载配置成功: {config}")