# 后台检查工具

用户只发[主文件](../muse-idea-to-short.md)给Muse即可。本目录供助手维护，不生成视频、不调用Muse、不发送消息；文本通过和规格通过都不等于故事/动态/发音通过。

## U0实际文件检查

Python标准库加已安装的官方FFmpeg/ffprobe；缺工具或字段记UNVERIFIED，不凭容器总时长、音轨或缩略图判定视频。默认720短边、0.01比例容差和scene阈值0.35都是待测预设；项目采用值优先。

`--scene-threshold`可覆盖疑似硬切阈值；排除封面流后仅扫描唯一视频主流，多个视频流不擅自选择。

```sh
python tools/u0_check.py downloaded.mp4 --target-aspect 0.5625 --min-seconds 6 --max-seconds 10 --min-short-side 720
```

画幅/视频流时长不符合采用目标FAIL；短边偏小、scene变化候选WARN“可能拼接”；没完成检测UNVERIFIED。旋转与像素/显示比例参与判断。硬切算法也会响应闪光/曝光，不证明自动拼接；连续内容/音轨另查。返回码PASS/WARN为0、FAIL为2、UNVERIFIED为3，自动化必须看JSON状态，不能把WARN当验收PASS。不改写原视频或自动重新提交。

## 输入检查格式

使用一个`### 制作任务`与同级`### 模型输入（原样转交）`，管理JSON仅留在制作层。`--card`可重复或不提供；纯文字设`text_only: true`，空参考不绕过已采用卡的必要图片。

````markdown
### 制作任务
```json
{"mode":"test","cards":[],"subject_count":0,"text_only":true,"references":[],"style_prefix":"9:16，二维插画","prompt_budget_seconds":10,"usable_window":[0,8],"required_event":"盒子移到B"}
```
### 模型输入（原样转交）
风格：9:16，二维插画
主体数：0
场景：柜台和一个蓝盒
0–2秒：蓝盒在A
2–5秒：蓝盒向B移动
5–8秒：蓝盒停在B
镜头：固定中景
声音：只有动作声
约束：无文字、无字幕、无水印
````

外层示意的Markdown围栏可去掉，保存为`shot.md`，运行：

```sh
python tools/lint_shot.py --shot shot.md --max-clip-seconds 10
```

默认检查禁字三项、无音乐/对白、单种机位、管理话术、规划容量10秒（待测）。用户已采用不同要求时制作JSON明确写`allow_music/allow_dialogue`、`planning_limit_seconds`和`policies.max_camera_moves/required_literals`；默认不得覆盖用户稿。`mode: detailed`必须提供`frozen_blocks`原文对象（character/style/scene/constraint等按实际有的项），逐字存在检查不保证视觉一致。

卡JSON支持`card_id/version/locked_text/style_prefix/constraint_block/reference_images/adoption_evidence`；详细模式也可将用户原话放`frozen_blocks`，不要求伪造不存在的人物。动作可为起点/动作/终点，或连续相对秒段。视觉“不要/禁止”给WARN供对照，不自动删除用户禁令。词法规则仅能发现明显冲突，不理解全部否定/中文同义词，场景、动作、参考上传与平台原文需真实复核。

## 维护

```sh
python -m unittest discover -s tools/tests -p "test_*.py"
python tools/check_package.py
```

字数按全部Unicode字符计算（含Markdown/空白），比只算中文字更保守；不生成主文件，检查失败直接改唯一主文件。实测表CSV仅有表头，实际投产时记录真实提交/文件/费用或unknown。维护取舍与失败来源见[重构记录](refactor-review.md)。
