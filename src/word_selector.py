# src/word_selector.py
"""纯单词选择逻辑：两阶段抽取 + 严格跨天跨池不重复（按英文单词字符串去重）。

两阶段抽取：先把每天的名额分配到各选中单元（每个仍有存货的单元保底 1 个，
其余名额按单元剩余可用词量加权随机分配），再在各单元内随机选词。
相比从合并大池直接抽样，可避免单词扎堆在个别单元、共享词被早期单元垄断。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
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


def _build_unit_pools(data: dict, units: List[str]) -> Dict[str, List[WordEntry]]:
    """按单元构建词池：{单元名: [WordEntry, ...]}。

    跨单元的重复词在各单元中各自保留（抽到哪个单元就用哪个单元的释义），
    整周期唯一性由抽取时的全局 used 集合保证。
    """
    pools: Dict[str, List[WordEntry]] = {}
    for unit in units:
        entries = [
            WordEntry(word=w['word'], translation=w['translation'], unit=unit)
            for w in data.get('unit_words', {}).get(unit, [])
        ]
        if entries:
            pools[unit] = entries
    return pools


def _unique_available(unit_pools: Dict[str, List[WordEntry]],
                      used: Set[str]) -> int:
    """去重后的可用单词数（按英文单词字符串，排除已用）。"""
    seen: Set[str] = set()
    for words in unit_pools.values():
        for w in words:
            if w.word not in used:
                seen.add(w.word)
    return len(seen)


def _pick_by_unit(unit_pools: Dict[str, List[WordEntry]], count: int,
                  used: Set[str], rng: random.Random) -> List[WordEntry]:
    """两阶段抽取 count 个单词。

    阶段一（名额分配）：打乱单元顺序，每个仍有可用词的单元保底 1 个名额；
    剩余名额按各单元剩余可用词量加权，随机分配到单元。
    阶段二（单元内选词）：每个名额在其单元的可用词中随机选一个。

    全程维护全局 used（按英文单词字符串），保证跨天跨池不重复。
    """
    if count <= 0:
        return []
    picked: List[WordEntry] = []

    # 阶段一 a：保底名额（顺序随机；名额少于单元数时随机决定哪些单元入选）
    guarantee_order = list(unit_pools)
    rng.shuffle(guarantee_order)
    for unit in guarantee_order:
        if len(picked) >= count:
            break
        avail = [w for w in unit_pools[unit] if w.word not in used]
        if avail:
            entry = rng.choice(avail)
            used.add(entry.word)
            picked.append(entry)

    # 阶段一 b + 阶段二：剩余名额按剩余可用量加权随机分配，并在选中单元内选词
    while len(picked) < count:
        avail_map = {
            unit: [w for w in words if w.word not in used]
            for unit, words in unit_pools.items()
        }
        avail_map = {unit: ws for unit, ws in avail_map.items() if ws}
        if not avail_map:  # 防御：逐日预检查应已拦截此情况
            raise SelectionError(
                "单词不足：可用单词已耗尽，请减少数量或选择更多单元。"
            )
        units = list(avail_map)
        weights = [len(avail_map[u]) for u in units]
        unit = rng.choices(units, weights=weights, k=1)[0]
        entry = rng.choice(avail_map[unit])
        used.add(entry.word)
        picked.append(entry)

    return picked


def select_words(
    data: dict,
    focus_units: List[str],
    review_units: List[str],
    focus_count: int,
    review_count: int,
    days: int,
    rng: Optional[random.Random] = None,
) -> List[DayPlan]:
    """选择单词：两阶段抽取，严格跨天不重复（按英文单词字符串）。

    每天的名额先在单元间分配（保底 1 个/单元 + 按剩余词量加权），
    再在单元内随机选词。重点与复习共享全局 used 集合：一个词一旦被
    选中，就不会再出现（无论重点还是复习、今天还是后续天）。

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

    focus_pools = _build_unit_pools(data, focus_units)
    review_pools = _build_unit_pools(data, review_units)

    # --- 快速预检查（必要但不充分，因为跨池可能共享词） ---
    focus_total = _unique_available(focus_pools, set())
    if focus_count > 0 and focus_total < focus_count * days:
        raise SelectionError(
            f"重点单词不足：需 {focus_count * days} 个（{focus_count}/天 × {days}天），"
            f"去重后仅 {focus_total} 个可用。\n"
            f"请减少天数或重点单词数，或选择更多重点单元。"
        )
    review_total = _unique_available(review_pools, set())
    if review_count > 0 and review_total < review_count * days:
        raise SelectionError(
            f"复习单词不足：需 {review_count * days} 个（{review_count}/天 × {days}天），"
            f"去重后仅 {review_total} 个可用。\n"
            f"请减少天数或复习单词数，或选择更多复习单元。"
        )

    # --- 逐天抽取 ---
    used: Set[str] = set()
    plans: List[DayPlan] = []

    for day in range(1, days + 1):
        # 重点单词（先抽：共享词会消耗复习池）
        if focus_count > 0:
            avail_n = _unique_available(focus_pools, used)
            if avail_n < focus_count:
                raise SelectionError(
                    f"第{day}天重点单词不足：还需 {focus_count} 个，"
                    f"去重后仅剩 {avail_n} 个可用（已被前几天或复习消耗）。\n"
                    f"请减少天数或重点单词数，或选择更多单元。"
                )
        focus_picked = _pick_by_unit(focus_pools, focus_count, used, rng)

        # 复习单词（重新计算可用量，因为重点可能已消耗共享词）
        if review_count > 0:
            avail_n = _unique_available(review_pools, used)
            if avail_n < review_count:
                raise SelectionError(
                    f"第{day}天复习单词不足：还需 {review_count} 个，"
                    f"去重后仅剩 {avail_n} 个可用（已被重点或前几天消耗）。\n"
                    f"请减少天数或复习单词数，或选择更多单元。"
                )
        review_picked = _pick_by_unit(review_pools, review_count, used, rng)

        plans.append(DayPlan(day_num=day, focus_words=focus_picked,
                             review_words=review_picked))

    return plans
