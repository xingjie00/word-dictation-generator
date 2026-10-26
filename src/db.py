# src/db.py
"""SQLite 词库存储层。

words.db 为运行时唯一数据源；首次运行（或库为空）时从 words.json 种子导入。
所有公开函数幂等（先 init_db），均可通过 db_path 参数指定数据库文件以便测试。
"""
import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.data_loader import get_data_file_path, get_resource_folder

DB_FILENAME = 'words.db'

# 两表设计：ORDER BY u.id, w.id 保持 JSON 追加语义（向早期单元加词不会打乱单元顺序）
# dictation_count 为抽查次数（被选入听写文档的累计次数），旧库经 _migrate 幂等补列
_SCHEMA = """
CREATE TABLE IF NOT EXISTS units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    word TEXT NOT NULL,
    translation TEXT NOT NULL,
    dictation_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE(unit_id, word)
);
"""


def get_db_path() -> str:
    """数据库文件路径（frozen 模式下为 exe 旁可写的 resources/words.db）。"""
    return os.path.join(get_resource_folder(), DB_FILENAME)


def _resolve(db_path: Optional[str]) -> str:
    return db_path if db_path is not None else get_db_path()


def _connect(db_path: str) -> sqlite3.Connection:
    """打开连接并启用外键（SQLite 默认关闭，不设则 FK/UNIQUE 的引用约束静默失效）。"""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _read_seed(seed_path: str) -> list:
    """读取种子 words.json 的 word_list。缺失/损坏抛 RuntimeError。"""
    if not os.path.exists(seed_path):
        raise RuntimeError(
            f"未找到种子数据文件 words.json（{seed_path}），无法初始化词库。\n"
            f"请确保该文件与程序位于同一目录结构中。"
        )
    try:
        with open(seed_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(f"读取种子数据文件失败：{e}") from e
    return data.get("word_list", [])


def _seed(conn: sqlite3.Connection, word_list: list) -> None:
    """将 word_list 导入数据库（单元内重复词保留首个，与选词器 first-wins 语义一致）。"""
    for unit_info in word_list:
        cur = conn.execute("INSERT INTO units (name) VALUES (?)", (unit_info["unit"],))
        unit_id = cur.lastrowid
        seen = set()
        rows = []
        for w in unit_info.get("words", []):
            if w["word"] in seen:
                continue
            seen.add(w["word"])
            rows.append((unit_id, w["word"], w["translation"]))
        if rows:
            conn.executemany(
                "INSERT INTO words (unit_id, word, translation) VALUES (?, ?, ?)", rows
            )


def _migrate(conn: sqlite3.Connection) -> None:
    """幂等迁移：旧库 words 表补 dictation_count 列（已有数据保持默认 0）。"""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(words)")]
    if 'dictation_count' not in cols:
        conn.execute(
            "ALTER TABLE words ADD COLUMN dictation_count INTEGER NOT NULL DEFAULT 0"
        )


def _init_once(db_path: str, seed_json: Optional[str]) -> None:
    """单次初始化尝试：建表 + 迁移 + 探针 + 视需要播种。sqlite 异常向上传播。"""
    conn = _connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        _migrate(conn)  # 旧库补列（幂等），在种子导入之前执行
        # 探针必须是真实查询：connect 不验证文件，损坏在首条语句才暴露
        count = conn.execute("SELECT COUNT(*) FROM units").fetchone()[0]
        if count == 0:
            seed_path = seed_json if seed_json is not None else get_data_file_path('words.json')
            word_list = _read_seed(seed_path)
            _seed(conn, word_list)
            conn.commit()
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None, seed_json: Optional[str] = None) -> Optional[str]:
    """初始化数据库（幂等）：建表；units 为空则从种子导入。

    Args:
        db_path: 数据库文件路径；None 用默认位置。
        seed_json: 种子 words.json 路径；None 用 get_data_file_path 解析（外部优先→内置）。

    Returns:
        若检测到损坏文件并已隔离，返回隔离文件路径；否则 None。
        调用方（GUI）应据此向用户显示警告。

    Raises:
        sqlite3.OperationalError: 数据库被锁/无权限（隔离改名解决不了，直接上抛）。
        RuntimeError: 种子缺失/损坏，或隔离后重建仍失败。
    """
    path = _resolve(db_path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    try:
        _init_once(path, seed_json)
        return None
    except sqlite3.OperationalError:
        # 锁/权限类问题：改名无意义，原样上抛
        raise
    except sqlite3.DatabaseError:
        # 文件损坏（非 OperationalError 子类的 DatabaseError）：隔离后重建一次
        quarantine = f"{path}.corrupt-{datetime.now():%Y%m%d-%H%M%S}"
        os.replace(path, quarantine)
        try:
            _init_once(path, seed_json)
        except sqlite3.DatabaseError as e:
            raise RuntimeError(f"数据库文件损坏且无法从种子恢复：{e}") from e
        return quarantine


def load_word_data(db_path: Optional[str] = None) -> Dict:
    """从数据库加载全部词库。

    Returns:
        {'units': [单元名...],
         'unit_words': {单元名: [{'id','word','translation','dictation_count'}...]}}
        与 word_selector 的数据契约一致（无 word_list 键）。
    """
    path = _resolve(db_path)
    init_db(path)
    conn = _connect(path)
    try:
        rows = conn.execute(
            "SELECT u.name, w.id, w.word, w.translation, w.dictation_count "
            "FROM units u LEFT JOIN words w ON w.unit_id = u.id "
            "ORDER BY u.id, w.id"
        ).fetchall()
    finally:
        conn.close()

    units: List[str] = []
    unit_words: Dict[str, List[Dict]] = {}
    for name, wid, word, translation, count in rows:
        if name not in unit_words:
            unit_words[name] = []
            units.append(name)
        if word is not None:  # LEFT JOIN：空单元保护
            unit_words[name].append({
                'id': wid, 'word': word, 'translation': translation,
                'dictation_count': count,
            })
    return {'units': units, 'unit_words': unit_words}


def get_unit_names(db_path: Optional[str] = None) -> List[str]:
    """全部单元名（按 id 顺序）。"""
    path = _resolve(db_path)
    init_db(path)
    conn = _connect(path)
    try:
        rows = conn.execute("SELECT name FROM units ORDER BY id").fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def unit_exists(name: str, db_path: Optional[str] = None) -> bool:
    """单元是否存在。"""
    path = _resolve(db_path)
    init_db(path)
    conn = _connect(path)
    try:
        row = conn.execute("SELECT 1 FROM units WHERE name = ?", (name,)).fetchone()
    finally:
        conn.close()
    return row is not None


def get_unit_words(unit_name: str, db_path: Optional[str] = None) -> List[Dict]:
    """指定单元的单词列表（按 id 顺序，含 id 与抽查次数）。"""
    path = _resolve(db_path)
    init_db(path)
    conn = _connect(path)
    try:
        rows = conn.execute(
            "SELECT w.id, w.word, w.translation, w.dictation_count FROM words w "
            "JOIN units u ON w.unit_id = u.id "
            "WHERE u.name = ? ORDER BY w.id",
            (unit_name,)
        ).fetchall()
    finally:
        conn.close()
    return [{'id': i, 'word': w, 'translation': t, 'dictation_count': c}
            for i, w, t, c in rows]


def add_unit(name: str, words: List[Tuple[str, str]], db_path: Optional[str] = None) -> bool:
    """新增单元及其单词（单事务）。

    Args:
        name: 单元名。
        words: [(word, translation), ...]
        db_path: 数据库路径；None 用默认。

    Returns:
        单元已存在返回 False（不写入）；成功返回 True。
        单元内重复词触发 sqlite3.IntegrityError（调用方应预检，UNIQUE 为兜底）。
    """
    path = _resolve(db_path)
    init_db(path)
    conn = _connect(path)
    try:
        row = conn.execute("SELECT id FROM units WHERE name = ?", (name,)).fetchone()
        if row is not None:
            return False
        cur = conn.execute("INSERT INTO units (name) VALUES (?)", (name,))
        unit_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO words (unit_id, word, translation) VALUES (?, ?, ?)",
            [(unit_id, w, t) for w, t in words]
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_words(unit_name: str, words: List[Tuple[str, str]], db_path: Optional[str] = None) -> bool:
    """向已有单元追加单词（单事务）。

    Args:
        unit_name: 目标单元名。
        words: [(word, translation), ...]
        db_path: 数据库路径；None 用默认。

    Returns:
        单元不存在返回 False；成功返回 True。
        单元内重复词触发 sqlite3.IntegrityError（调用方应预检，UNIQUE 为兜底）。
    """
    path = _resolve(db_path)
    init_db(path)
    conn = _connect(path)
    try:
        row = conn.execute("SELECT id FROM units WHERE name = ?", (unit_name,)).fetchone()
        if row is None:
            return False
        unit_id = row[0]
        conn.executemany(
            "INSERT INTO words (unit_id, word, translation) VALUES (?, ?, ?)",
            [(unit_id, w, t) for w, t in words]
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def increment_dictation_counts(word_ids: List[int],
                               db_path: Optional[str] = None) -> None:
    """批量累加单词抽查次数（单事务，任一失败整体回滚）。

    Args:
        word_ids: 单词 id 列表；同一 id 出现多次则累加多次
            （同一文档中被抽中多天、或同一天既作重点又作复习）。
        db_path: 数据库路径；None 用默认。
    """
    if not word_ids:
        return
    path = _resolve(db_path)
    init_db(path)
    conn = _connect(path)
    try:
        conn.executemany(
            "UPDATE words SET dictation_count = dictation_count + 1 WHERE id = ?",
            [(i,) for i in word_ids]
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
