# 一句话成片 · muse-idea-to-short

让 Muse 把一句话、一段大纲或一段长提示词，做成30秒以上、多镜头、角色前后一致的短片。

**什么时候用**：要的片子超过10秒，需要拆成多镜再拼起来；或者有台词、有重复出现的角色。

**什么时候别用**：只要一条10秒左右的视频，直接给 Muse 就行（skill 也会识别出来，直接放行）。

**怎么发**：把[主文件](muse-idea-to-short.md)发给 Muse（读不了链接就把正文贴进去），再说你要什么。任何写法都可以：一句话、大纲、分段时间码、一整段英文提示词都行。Muse 会先交一张故事板和主角定妆图，你回“可以”，它就一路做到交整片。不想确认就加一句“自主成片”。

**拿到片子先看**：人是不是同一个、镜头之间接得顺不顺、台词对不对、画幅对不对、结尾能不能看清主角。

> 按《一句话成片》做一条30秒、竖屏9:16的治愈动画：蓝外套小兔把迷路的萤火虫带回灯笼。先给我故事板和小兔的定妆图，我说可以之后就一直做到交整片。

## v3 的思路
旧版把运镜、拍数、音乐、对白都卡死了，还要求大量记账，结果约束了 Muse 本来的能力，效果反而不如直接用。v3 反过来：

- **不替 Muse 写画面**。画面、运镜、音乐、节奏都交给 Muse 自己发挥。
- **只补三个短板**：长片拆镜与拼接、角色一致（锚点句加定妆图）、说话（原生对白、画外音、无对白三选一）。
- **任何输入先整理成同一张故事板**，所以提示词怎么写都可以，后面的流程都一样。
- **只确认一次**：故事板加定妆图。

## 文件
- [主文件](muse-idea-to-short.md)：唯一的规则，发给 Muse 的就是它。
- 题材包（按需）：[治愈小角色](genres/healing-ip.md) / [写实人物出镜 · meinv-chujing](genres/beauty-oncamera.md) / [真人古风](genres/guofeng-live.md)
- 示例：[一句话→故事板](examples/one-line.md) / [带时间码的长提示词→拆镜](examples/detailed-prompt.md) / [两人对话戏](examples/dialogue-scene.md) / [10/03 的45秒翻车记录](examples/case-2026-10-03-healing-45s.md)
- **测试**：[固定测试集](testing/test-set.md)、[评分表](testing/scorecard.md)、[结果记录](testing/results.csv)。每次改 skill，都用同一批输入做“有 skill / 没 skill”对照。

v3 还没有用 Muse 实际测过，效果要靠测试集来验证。

## 给助手宿主使用

```sh
git clone https://github.com/toosielu/muse-idea-to-short.git ~/.codex/skills/muse-idea-to-short
```

调用：`$muse-idea-to-short`。入口是 [SKILL.md](SKILL.md)。

## 维护与检查

```sh
python -m unittest discover -s tools/tests -p "test_*.py"
python tools/check_package.py
```

[工具说明](tools/README.md)：怎样在本地量视频的画幅和时长。
