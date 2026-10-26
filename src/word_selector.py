# src/word_selector.py
"""纯单词选择逻辑：严格跨天不重复（按英文单词字符串去重）。"""
from dataclasses import dataclass, field
from typing import List, Optional
import random


@dataclass
class WordEntry:
    word: str
    translation: str
    unit: str


@dataclass
class DayPlan:
    day_num: int
    focus_words: List[WordEntry] = field(default_factory=list)
    review_words: List[WordEntry] = field(default_factory=list)


class SelectionError(Exception):
    """单词选择不足时抛出的异常。"""
    pass


def _build_pool(data: dict, units: List[str]) -> List[WordEntry]:
    """从指定单元构建单词池，按英文单词字符串去重（首次出现的释义胜出）。

    Args:
        data: load_word_data() 返回的数据，包含 'unit_words' 映射。
        units: 要纳入的单元名称列表。

    Returns:
        去重后的 WordEntry 列表。
    """
    pool: List[WordEntry] = []
    seen: set = set()
    for unit in units:
        for w in data.get('unit_words', {}).get(unit, []):
            word_str = w['word']
            if word_str in seen:
                continue
            seen.add(word_str)
            pool.append(WordEntry(word=word_str, translation=w['translation'], unit=unit))
    return pool


def select_words(
    data: dict,
    focus_units: List[str],
    review_units: List[str],
    focus_count: int,
    review_count: int,
    days: int,
    rng: Optional[random.Random] = None,
) -> List[DayPlan]:
    """选择单词，严格跨天不重复（按英文单词字符串）。

    重点与复习共享全局 used 集合：一个词一旦被重点选中，就不会再出现在复习中，
    反之亦然。每天抽取前重新计算可用池，确保正确性。

    Args:
        data: load_word_data() 返回的数据。
        focus_units: 重点单元名称列表。
        review_units: 复习单元名称列表。
        focus_count: 每天重点单词数。
        review_count: 每天复习单词数。
        days: 练习天数。
        rng: 随机数生成器（可 seed，默认 random.Random()）。

    Returns:
        长度为 days 的 DayPlan 列表。

    Raises:
        SelectionError: 单词不足时抛出，消息包含可操作的建议。
    """
    if rng is None:
        rng = random.Random()

    focus_pool = _build_pool(data, focus_units)
    review_pool = _build_pool(data, review_units)

    # --- 快速预检查（必要但不充分，因为跨池可能共享词） ---
    if focus_count > 0 and len(focus_pool) < focus_count * days:
        raise SelectionError(
            f"重点单词不足：需 {focus_count * days} 个（{focus_count}/天 × {days}天），"
            f"去重后仅 {len(focus_pool)} 个可用。\n"
            f"请减少天数或重点单词数，或选择更多重点单元。"
        )
    if review_count > 0 and len(review_pool) < review_count * days:
        raise SelectionError(
            f"复习单词不足：需 {review_count * days} 个（{review_count}/天 × {days}天），"
            f"去重后仅 {len(review_pool)} 个可用。\n"
            f"请减少天数或复习单词数，或选择更多复习单元。"
        )

    # --- 逐天抽取 ---
    used: set = set()  # 全局已用单词（word 字符串）
    plans: List[DayPlan] = []

    for day in range(1, days + 1):
        # 重点单词
        focus_avail = [w for w in focus_pool if w.word not in used]
        if focus_count > 0 and len(focus_avail) < focus_count:
            raise SelectionError(
                f"第{day}天重点单词不足：还需 {focus_count} 个，"
                f"去重后仅剩 {len(focus_avail)} 个可用（已被前几天或复习消耗）。\n"
                f"请减少天数或重点单词数，或选择更多单元。"
            )
        focus_picked = rng.sample(focus_avail, focus_count) if focus_count > 0 else []
        for w in focus_picked:
            used.add(w.word)

        # 复习单词（重新计算可用池，因为重点可能已消耗共享词）
        review_avail = [w for w in review_pool if w.word not in used]
        if review_count > 0 and len(review_avail) < review_count:
            raise SelectionError(
                f"第{day}天复习单词不足：还需 {review_count} 个，"
                f"去重后仅剩 {len(review_avail)} 个可用（已被重点或前几天消耗）。\n"
                f"请减少天数或复习单词数，或选择更多复习单元。"
            )
        review_picked = rng.sample(review_avail, review_count) if review_count > 0 else []
        for w in review_picked:
            used.add(w.word)

        plans.append(DayPlan(day_num=day, focus_words=focus_picked, review_words=review_picked))

    return plans
