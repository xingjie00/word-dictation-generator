# src/config_manager.py
import json
import os
import sys
from typing import Dict, Any


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


class ConfigManager:
    """配置管理类"""

    def __init__(self, config_file=None):
        print("=== ConfigManager 初始化调试 ===")
        print(f"当前文件: {__file__}")

        if config_file is None:
            # 获取正确的配置文件路径
            if getattr(sys, 'frozen', False):
                # 如果是打包后的exe
                base_path = sys._MEIPASS
                print(f"打包模式 - base_path: {base_path}")

                # 默认配置在exe内部（只读）
                self.default_config_file = os.path.join(base_path, 'resources', 'config.json')
                # 用户配置在exe所在目录（可写）
                exe_dir = os.path.dirname(sys.executable)
                self.user_config_file = os.path.join(exe_dir, 'resources', 'config.json')

                print(f"打包模式 - default_config_file: {self.default_config_file}")
                print(f"打包模式 - user_config_file: {self.user_config_file}")
            else:
                # 开发环境
                # 查找项目根目录
                project_root = find_project_root()
                print(f"开发模式 - 项目根目录: {project_root}")

                self.default_config_file = os.path.join(project_root, 'resources', 'config.json')
                self.user_config_file = self.default_config_file

                print(f"开发模式 - config_file: {self.default_config_file}")
        else:
            # 如果传入了具体路径，直接使用
            self.default_config_file = config_file
            self.user_config_file = config_file
            print(f"自定义路径 - config_file: {config_file}")

        print(f"默认配置文件存在: {os.path.exists(self.default_config_file)}")
        print(f"用户配置文件存在: {os.path.exists(self.user_config_file)}")
        print("=== 初始化完成 ===\n")

        self.default_config = {
            'focus_count': 10,
            'total_count': 18,
            'days': 5,
            'filename': '单词听写'
        }

    def load(self) -> Dict[str, Any]:
        """加载配置：优先读取用户配置，不存在则读取默认配置"""
        print("=== 加载配置调试 ===")
        print(f"用户配置文件: {self.user_config_file}")
        print(f"默认配置文件: {self.default_config_file}")

        try:
            # 优先尝试用户配置
            if os.path.exists(self.user_config_file):
                print("✅ 使用用户配置文件")
                return self._load_from_file(self.user_config_file)
            # 用户配置不存在，尝试默认配置
            elif os.path.exists(self.default_config_file):
                print("⚠️ 用户配置不存在，使用默认配置文件")
                return self._load_from_file(self.default_config_file)
            else:
                print("⚠️ 配置文件都不存在，使用默认配置值")
                return self.default_config.copy()
        except Exception as e:
            print(f"❌ 加载配置异常: {e}，使用默认配置值")
            return self.default_config.copy()

    def _load_from_file(self, filepath: str) -> Dict[str, Any]:
        """从指定文件加载配置"""
        print(f"从文件加载: {filepath}")
        print(f"文件存在: {os.path.exists(filepath)}")

        with open(filepath, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # 确保所有配置项都存在
            for key, value in self.default_config.items():
                if key not in config:
                    config[key] = value
            print(f"加载的配置: {config}")
            return config

    def save(self, config: Dict[str, Any]) -> bool:
        """保存配置：总是保存到用户配置"""
        print("=== 保存配置调试 ===")
        print(f"保存到文件: {self.user_config_file}")
        print(f"保存的配置: {config}")

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.user_config_file), exist_ok=True)
            print(f"确保目录存在: {os.path.dirname(self.user_config_file)}")

            with open(self.user_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print("✅ 配置保存成功")
            return True
        except Exception as e:
            print(f"❌ 保存配置失败: {e}")
            return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """验证并修正配置"""
        print("=== 验证配置调试 ===")
        print(f"原始配置: {config}")

        validated = config.copy()

        # 验证数字范围
        validated['focus_count'] = max(0, min(config.get('focus_count', 10), 50))
        validated['total_count'] = max(1, min(config.get('total_count', 18), 100))
        validated['days'] = max(1, min(config.get('days', 5), 30))

        # 确保重点单词数不超过总单词数
        if validated['focus_count'] > validated['total_count']:
            validated['focus_count'] = validated['total_count']

        print(f"验证后配置: {validated}")
        return validated


# 测试函数
def test_config_manager():
    """测试配置管理器"""
    print("🚀 测试 ConfigManager")
    print("=" * 50)

    # 创建配置管理器
    config_manager = ConfigManager()

    # 测试加载配置
    print("\n📥 测试加载配置:")
    config = config_manager.load()

    # 测试验证配置
    print("\n🔍 测试验证配置:")
    test_config = {'focus_count': 100, 'total_count': 5, 'days': 40, 'filename': '测试'}
    validated = config_manager.validate_config(test_config)

    # 测试保存配置
    print("\n💾 测试保存配置:")
    config['test_timestamp'] = '2024-01-01 12:00:00'
    saved = config_manager.save(config)

    print(f"\n✅ 测试完成，保存结果: {saved}")


if __name__ == "__main__":
    test_config_manager()