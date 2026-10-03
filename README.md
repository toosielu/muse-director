# 一句话成片 · muse-idea-to-short

**什么时候用**：你有一句话、简单故事，或比较长的提示词，希望做成 30 秒以上的多镜头短片，并且角色前后是同一个。

**什么时候别用**：只要一条约 10 秒的视频，或已经写好每一镜的提示词，通常直接给 Muse 更合适。需要拆开再接起来时，用入口 B。

**怎么发**：把[主文件](muse-idea-to-short.md)发给 Muse，再加上主题、时长和画幅。请求像治愈小角色、写实人物出镜或真人古风时，让它先读对应的题材包。默认会停三次等你说可以：分镜表、每个重复角色的角色卡、主角定妆。想让它不问就做完，加一句「自主成片」。定妆仍然要做，不能省。Muse 读不了链接时，把正文贴进去。

**拿到片子先看**：故事有没有漏、人物是不是同一个人（耳朵、道具、材质、比例）、场景有没有乱跳、最后一镜主角能不能看清、时长和画幅对不对。画幅量不到不能算通过。只看截图不算看完整片。

> 请读取《一句话成片》。做一条 30 秒以上、竖屏 9:16 的治愈动画：蓝外套小兔带迷路萤火虫回灯笼。先给分镜表等我点头，再给小兔和萤火虫的角色卡，主角做 3 条定妆等我点头，然后生成、检查、剪辑，交能播放的整片。每条提示词都写上画幅。

## 按需补充

- [一句话→4镜30秒](examples/one-line-to-30s.md)
- [已有详细提示词：拆镜与原话合并](examples/prompt-merge.md)
- [治愈定妆实测：三条输入、回传与人工评分](examples/healing-test.md)
- [2026-10-03：45秒治愈成片翻车记录](examples/case-2026-10-03-healing-45s.md)
- [治愈IP](genres/healing-ip.md) / [写实人物出镜 · meinv-chujing](genres/beauty-oncamera.md) / [真人古风](genres/guofeng-live.md)

主文件是唯一制作规则。题材包只补这一类片子的知识，示例是教学稿。没在本项目用 Muse 测过的做法，在主文件开头标一次**待测**，不承诺画质、速度或成功率。生成仍然由 Muse 做。研究别的工具只学做法，不要求换模型，也不调用接口。

## 给助手宿主使用

把仓库克隆到 `~/.codex/skills/muse-idea-to-short`（其他助手用自己的技能目录）：

```sh
git clone https://github.com/toosielu/muse-idea-to-short.git ~/.codex/skills/muse-idea-to-short
```

调用：`$muse-idea-to-short`。入口 [SKILL.md](SKILL.md) 只负责指到主文件。直接把主文件交给 Muse 时，不用安装 Python，也不表示 Muse 自己带了技能安装。

## 维护与检查

```sh
python -m unittest discover -s tools/tests -p "test_*.py"
python tools/check_package.py
```

后台 [工具说明](tools/README.md) 写了怎样量本地视频、怎样检查提示词。工具不调用 Muse、不发消息，也不能代替看片。`tools/test-log.csv` 只有表头，不是已经做过的数据。默认值为什么这样取、以及 2026-10-03 那次成片之后改了哪条默认，见 [重构记录](tools/refactor-review.md)。
