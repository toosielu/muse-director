# 一句话成片 · muse-idea-to-short

**什么时候用**：你有一句话、简单故事，或15/30秒以上的详细提示词，希望Muse做成多镜头短片并保持角色连续性。

**什么时候别用**：只要一条约10秒视频，或已有完整逐镜提示词，通常直接给Muse更合适；需要拆镜和整合时可使用入口B。

**怎么发**：下载 [主文件](muse-idea-to-short.md) 发给Muse，再给主题/剧本/提示词、时长、画幅及预算；无需上传整个仓库。默认逐镜确认；要直接拿整片，加一句“自主成片，普通选择不用问我”。Muse无法读GitHub时上传正文。

**拿到片子先看**：故事有没有漏、人物是否变脸、动作是否发生、台词/噪声是否正确、相邻镜头是否接上，以及时长/画幅是否符合要求。只有抽帧或技术通过不等于完整审片。

> 请读取《一句话成片》，自主完成30秒竖屏治愈动画：蓝外套小兔带迷路萤火虫回灯笼。普通选择你决定，保留必要事件，不新增购买、不超现有额度，最后交可播放下载全片和真实缺项。

## 按需补充

- [一句话→4镜30秒](examples/one-line-to-30s.md)
- [已有详细提示词：拆镜与原话合并](examples/prompt-merge.md)
- [治愈定妆实测：三条输入、回传与人工评分](examples/healing-test.md)
- [治愈IP](genres/healing-ip.md) / [写实人物出镜 · meinv-chujing](genres/beauty-oncamera.md) / [真人古风](genres/guofeng-live.md)

主文件是唯一制作规则；题材只补本题材知识，示例是未投产的教学稿。所有未在本项目Muse实测的默认值均标**待测**，没有真实生成质量、速度或成功率承诺。Muse仍是生成方，研究Seedance/Hell Grind只提取方法，不要求换模型或调用API。

## 给助手宿主使用

将仓库克隆到 `~/.codex/skills/muse-idea-to-short`（其他宿主用各自Skill目录）：

合并到main后安装：

```sh
git clone https://github.com/toosielu/muse-idea-to-short.git ~/.codex/skills/muse-idea-to-short
```

本次PR尚未合并时，预览安装用 `git clone --branch codex/idea-to-short-refactor https://github.com/toosielu/muse-idea-to-short.git ~/.codex/skills/muse-idea-to-short`，直接交Muse也请下载该分支的主文件。旧安装目录先备份移出Skill目录，再安装新名称，避免双入口。

调用：`$muse-idea-to-short`。入口 [SKILL.md](SKILL.md) 只路由到主文件。直接用Muse无需Python，也不表示Muse支持原生Skill安装。

## 维护与检查

```sh
python -m unittest discover -s tools/tests -p "test_*.py"
python tools/check_package.py
```

后台 [工具说明](tools/README.md) 包含U0与提示词检查用法；工具不调用Muse、不发消息、不承担语义审片。`tools/test-log.csv` 是空的实测记录表，不是已执行数据。默认值对照、Jarvis来源失败记录、C1–C8处理和逐条验收见 [重构记录](tools/refactor-review.md)。旧规则层已移除，不再自动拼指南。
