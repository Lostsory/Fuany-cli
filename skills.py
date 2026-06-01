"""skill 渐进披露:扫描 skills/ → listing 进 prompt(便宜)→ 全文按需 load(贵)。

对照 Claude Code:
  - loadSkillsDir.ts:185-265  frontmatter 解析
  - attachments.ts:2661       listing 注入(system-reminder)
  - SkillTool.ts              全文按需加载

mini-cc 简化:手写 frontmatter 解析(不引 pyyaml,字段简单)。
"""

from dataclasses import dataclass

from config import SKILL_DIR


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """解析 SKILL.md:--- 之间是简单 key: value frontmatter,之后是 body。

    只支持单行 key: value(mini-cc 够用),不支持嵌套/多行 YAML —— 这是
    "frontmatter 不等于需要完整 YAML 解析器" 的刻意简化。
    """
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)  # ['', frontmatter, body]

    if len(parts) < 3:
        return {}, text

    fm: dict[str, str] = {}

    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()

    return fm, parts[2].strip()


_cache: tuple[Skill, ...] | None = None
_cache_fingerprint: frozenset[tuple[str, float]] = frozenset()


def discover_skills() -> tuple[Skill, ...]:
    """扫描 SKILL_DIR,解析每个 <name>/SKILL.md(渐进披露 Layer 1 的数据源)。

    内存缓存 + 文件指纹失效(对照 Hermes 缓存层):指纹 = 所有 SKILL.md 的
    (路径, mtime) 集合,加/删/改任一种 → 指纹变 → 重扫,否则用缓存。
    比 @cache 强:能感知运行时新增/修改 skill。
    """

    global _cache, _cache_fingerprint
    if not SKILL_DIR.is_dir():
        return ()

    md_files = sorted(SKILL_DIR.rglob("SKILL.md"))

    fingerprint = frozenset((str(p), p.stat().st_mtime) for p in md_files)

    if _cache is not None and fingerprint == _cache_fingerprint:
        return _cache

    skills: list[Skill] = []
    for md in md_files:
        fm, body = _parse_frontmatter(md.read_text(encoding="utf-8"))
        skills.append(
            Skill(
                name=fm.get("name", md.parent.name),  # ← md.parent.name = <name> 目录名
                description=fm.get("description", ""),
                body=body,
            )
        )
    _cache = tuple(skills)
    _cache_fingerprint = fingerprint
    return _cache


def skill_reminder() -> str | None:
    """渐进披露 Layer 1:生成 skill listing reminder。无 skill 返回 None。"""
    skills = discover_skills()
    if not skills:
        return None
    lines = "\n".join(f"- {s.name}: {s.description}" for s in skills)
    return (
        "## 可用 Skills\n"
        "下面是可用的专门指南。需要某个时,用 load_skill(name) 加载它的完整内容:\n"
        f"{lines}"
    )


def load_skill_body(name: str) -> str | None:
    """渐进披露 Layer 2:读指定 skill 的全文 body。"""
    for s in discover_skills():
        if s.name == name:
            return s.body
    return None
