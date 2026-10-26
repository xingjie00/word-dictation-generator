# src/word_selector.py
"""纯单词选择逻辑：每天独立抽取，仅要求当天不重复。

每天的名额分两阶段分配：
1. 按随机权重把名额分到各选中单元——权重为以单元词量为参数的
   Dirichlet 随机数（期望比例≈词量比例，带随机波动），名额不少于
   单元数的场景下每单元保底 1 个，且不超过其可用词量；
2. 在各单元内随机选词。

跨天允许重复（复习的间隔重复语义）；同一天内重点/复习/各单元之间
按英文单词字符串去重，保证当天不重复。
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
    当天唯一性由抽取时的 day_used 集合保证。
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


def _allocate_quotas(avail_counts: Dict[str, int], count: int,
                     rng: random.Random) -> Dict[str, int]:
    """按随机权重在单元间分配 count 个名额。

    权重为 Dirichlet 随机数（以各单元可用词量为集中度参数）：
    期望比例≈词量比例，带随机波动。count ≥ 单元数时每单元保底 1 个；
    任何单元的名额不超过其可用词量，被上限截走的名额顺延给其他单元
    （仍填不满的部分由调用方的回填循环兜底）。
    """
    units = list(avail_counts)
    quotas = {u: 0 for u in units}

    # 保底名额
    if count >= len(units):
        for u in units:
            quotas[u] = min(1, avail_counts[u])

    remaining = count - sum(quotas.values())
    if remaining <= 0:
        return quotas

    # 随机权重（Dirichlet：alpha = 可用词量）
    gammas = [rng.gammavariate(max(avail_counts[u], 1.0), 1.0) for u in units]
    total = sum(gammas)
    if total > 0:
        weights = [g / total for g in gammas]
    else:  # 理论上不会发生，防御
        weights = [1.0 / len(units)] * len(units)
    raw = {u: remaining * w for u, w in zip(units, weights)}

    # 期望名额取整（受单元上限约束）
    for u in units:
        add = min(int(raw[u]), avail_counts[u] - quotas[u])
        if add > 0:
            quotas[u] += add

    # 余数按小数部分从大到小补齐（同样受上限约束）
    leftover = count - sum(quotas.values())
    order = sorted(units, key=lambda u: raw[u] - int(raw[u]), reverse=True)
    while leftover > 0:
        progressed = False
        for u in order:
            if leftover <= 0:
                break
            if quotas[u] < avail_counts[u]:
                quotas[u] += 1
                leftover -= 1
                progressed = True
        if not progressed:
            break  # 全部单元到达上限，剩余名额交给回填循环
    return quotas


def _pick_by_unit(unit_pools: Dict[str, List[WordEntry]], count: int,
                  day_used: Set[str], rng: random.Random) -> List[WordEntry]:
    """单日抽取 count 个单词（两阶段：随机权重分配名额 + 单元内随机选词）。

    day_used 为当天已用单词集合（重点/复习共享），保证当天不重复；
    跨天无任何约束。
    """
    if count <= 0:
        return []
    picked: List[WordEntry] = []

    # 阶段一：随机权重分配名额（当天可用 = 排除 day_used 后的存量）
    avail_lists = {
        u: [w for w in ws if w.word not in day_used]
        for u, ws in unit_pools.items()
    }
    avail_lists = {u: ws for u, ws in avail_lists.items() if ws}
    if avail_lists:
        quotas = _allocate_quotas(
            {u: len(ws) for u, ws in avail_lists.items()}, count, rng
        )
        # 阶段二：单元内随机选词（后续单元排除当天已被前面单元选走的词）
        for unit, quota in quotas.items():
            if quota <= 0:
                continue
            avail = [w for w in avail_lists[unit] if w.word not in day_used]
            take = min(quota, len(avail))
            for entry in rng.sample(avail, take):
                day_used.add(entry.word)
                picked.append(entry)

    # 回填：名额因跨单元重复词或单元上限未填满时，按剩余可用量加权补齐
    while len(picked) < count:
        avail_map = {
            u: [w for w in ws if w.word not in day_used]
            for u, ws in unit_pools.items()
        }
        avail_map = {u: ws for u, ws in avail_map.items() if ws}
        if not avail_map:  # 防御：逐日预检查应已拦截此情况
            raise SelectionError(
                "单词不足：当天可用单词已耗尽，请减少数量或选择更多单元。"
            )
        units = list(avail_map)
        weights = [len(avail_map[u]) for u in units]
        unit = rng.choices(units, weights=weights, k=1)[0]
        entry = rng.choice(avail_map[unit])
        day_used.add(entry.word)
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
    """选择单词：每天独立抽取，仅保证当天不重复。

    每天的名额先按随机权重分配到各单元（保底 1 个/单元 + 其余按
    词量加权的 Dirichlet 随机权重），再在单元内随机选词。跨天允许
    重复（复习的间隔重复语义）；同一天内重点与复习共享 day_used，
    一个词当天只会出现一次。

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

    # --- 预检查：单日所需的去重后词量（每天独立抽取，只看单日） ---
    focus_total = _unique_available(focus_pools, set())
    if focus_count > 0 and focus_total < focus_count:
        raise SelectionError(
            f"重点单词不足：每天需 {focus_count} 个，"
            f"去重后仅 {focus_total} 个可用。\n"
            f"请减少重点单词数，或选择更多重点单元。"
        )
    review_total = _unique_available(review_pools, set())
    if review_count > 0 and review_total < review_count:
        raise SelectionError(
            f"复习单词不足：每天需 {review_count} 个，"
            f"去重后仅 {review_total} 个可用。\n"
            f"请减少复习单词数，或选择更多复习单元。"
        )

    # --- 逐天独立抽取 ---
    plans: List[DayPlan] = []
    for day in range(1, days + 1):
        day_used: Set[str] = set()  # 当天已用（重点/复习共享）

        focus_picked = _pick_by_unit(focus_pools, focus_count, day_used, rng)

        # 重点当天占用的共享词会压缩复习池，逐日复核
        if review_count > 0:
            avail_n = _unique_available(review_pools, day_used)
            if avail_n < review_count:
                raise SelectionError(
                    f"第{day}天复习单词不足：还需 {review_count} 个，"
                    f"去重后仅剩 {avail_n} 个可用（当天已被重点占用）。\n"
                    f"请减少复习单词数，或选择更多复习单元。"
                )
        review_picked = _pick_by_unit(review_pools, review_count, day_used, rng)

        plans.append(DayPlan(day_num=day, focus_words=focus_picked,
                             review_words=review_picked))

    return plans
