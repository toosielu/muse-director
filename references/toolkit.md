# 本地工作包和文件检查工具

`scripts/muse_pipeline.py` 使用 Python 标准库。探测和解码需要现有 FFprobe/FFmpeg；缺失时报告未检查，不安装工具或假报通过。通过 `load_workspace_dependencies` 定位可用 Python，也可使用已配置的 `python`。

下列 `python` 代表实际可用的解释器，`<skill>`、`<project>`、`<media>` 代表本技能目录、当前项目目录和本轮媒体文件，运行前替换为实际路径。路径用引号包裹；输出目录必须尚不存在，每轮采用新目录，保留旧报告的来源关系。模板见 [workflow-template.json](../assets/workflow-template.json)；交由当前助手按实际简报填写，不要求用户手工编辑 JSON。

## 固化一轮工作单

```powershell
python "<skill>/scripts/muse_pipeline.py" snapshot --project-root "<project>" --config "<project>/production-control/workflow.json" --output-dir "<project>/production-control/round-001"
```

输入配置使用以下结构；填写实际信息，不沿用其他项目的人物、声音或限制。每轮根据当前工作单构造新配置。工作单的授权只记录真实范围，不自动提升权限。

```json
{
  "schema_version": 1,
  "project_name": "实际项目名",
  "episode": "实际集数",
  "task_id": "本轮唯一任务标识",
  "thread_url": null,
  "baseline": {
    "script_version": "采用剧本版本",
    "visual_version": "采用画面版本或尚未制作",
    "approval_evidence": null
  },
  "phase": "preparation",
  "sources": [{"path": "已存在的采用任务书.md", "role": "执行依据"}],
  "constraints": [],
  "decisions": [],
  "issues": [],
  "deliverables": [],
  "authorization": {"mode": "prepare_only", "evidence": null},
  "next_action": "本轮可执行的下一步"
}
```

`decisions` 的项目含 `id/value/status/evidence`，status 为 `confirmed/provisional/pending`。`issues` 的项目含 `id/timecode/observation/required_change/acceptance/status/evidence`，尚未解决用 `open`；关闭必须记录证据。资料字段不会被当成命令执行，空证据会保留为待核验。

`sources` 的每项包含 project-root 内相对 `path` 和 `role`。工具解析实际路径并拒绝根目录外的来源。仅加入当前任务需要的材料，不把整部历史档案全部给 Muse。

输出包括 `packet.json`、`handoff.md` 和来源快照。记录来源摘要以便检测漂移。交接单是待发送文本；本地来源快照不等于 Muse 已收到附件。需要发送时将必要内容粘贴或使用实际附件/授权链接。

## 检查工作单是否过时

```powershell
python "<skill>/scripts/muse_pipeline.py" status --packet "<project>/production-control/round-001/packet.json"
```

只读核对原始来源、快照和工作包摘要，显示阶段、未定项和待办。原稿变化、丢失或工作包被改动时提示需要更新；不会静默重写快照。

这不是 Muse 云状态查询。原稿没变化仍可能有新 Muse 回传，因此下一次投产前还需恢复相关线程最新消息。相同问题没有进展时不频繁整页轮询；已有自动化请求才创建后续监测。

## 检查真实媒体

```powershell
python "<skill>/scripts/muse_pipeline.py" inspect --media "<media>" --output-dir "<project>/production-control/inspection-001" --decode --task-id "本轮任务ID" --declared-version "实际候选版本"
```

输出 `media-inspection.json`，绑定媒体路径及 SHA-256，记录元数据、音轨、技术检查和检查范围。`--task-id` 与 `--declared-version` 可选，只记录已知关联，默认 null。`--decode` 做实际解码；缺工具、探测/解码失败或检查期间文件变化不能通过。仅探测而未解码时整体为部分检查。

FFprobe/FFmpeg 默认从当前环境寻找；有工具但未加入搜索路径时，分别用 `--ffprobe`、`--ffmpeg` 指定实际程序路径。任务ID与版本是声明，不能靠文件名沿用旧“通过”。

先检查回传媒体，再将媒体和检查报告作为该轮 snapshot 的来源，这样工作包同时绑定任务 ID、媒体摘要和证据，`status` 可以发现原媒体变化。状态读取本身不写报告；有未定项或漂移返回码 2，属于需要处理的业务状态。输入错误或输出已存在返回 1。

报告中的语义项仍未核验；结果解释与采用判定见 [审查覆盖](workflow.md#审查覆盖)。

## 第一版边界

此工具不下载、不上传、不发消息、不生成媒体、不进行镜头对齐或声音识别，也不自动维护所有生产消息和附件。它先解决可重复的来源冻结、状态漂移和文件检查。

后续若有真实需求，再加入按时间戳采样、镜头映射比较、分轨/附件登记和事件记录。具体项目的旧诊断脚本需适配输入路径、采样时间与画面区域；不直接泛用硬编码坐标。
