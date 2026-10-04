# 2026-10-04 能力问答与实测

用户向 Muse 提了一组关于视频生成能力的问题，Muse 回答后当场生成了三条演示视频。下面分开记录“Muse 自己说的”和“实际生成结果”。前者是经验之谈，后者才算证据。

## 实测结果

|演示|输入|结果|
|---|---|---|
|A1|Jolly 定妆图＋挥手提示词|主角是**紫色水母**；前5秒底部烧录了英文字幕 “Hello there!”；1216×624|
|A2|同一张定妆图＋旋转提示词|主角是**白色毛茸茸小兽**；第一帧几乎就是定妆图原画面（花园、夕阳、背景水母），之后场景变成珊瑚礁；1216×624|
|B|苏巧基准形象图＋15字中文台词|脸型、挽发、米色卫衣、卧室暖灯都和形象图一致；嘴有张合，有人声；没有字幕；1152×768。读音和口型未核对（Muse 听不见）|

三条都是一次生成，每条约54秒。

### 实际发出的提示词
A1（参考图 `jolly-canonical-ref.png`）：
```
Jellyfish character Jolly, big round fluffy head, dot eyes, small smile, pink blush. Jolly floats above a coral reef and gently waves one tentacle at the camera. Soft underwater light. No text, no subtitles, no watermark.
```
A2（同一张参考图）：
```
Jellyfish character Jolly, big round fluffy head, dot eyes, small smile, pink blush. Jolly spins around once playfully, then drifts upward through soft light rays. Coral reef background. No text, no subtitles, no watermark.
```
B（参考图：苏巧基准形象图）：
```
A young Chinese woman in a cozy bedroom at night, facing the camera, medium close-up, speaks directly to the camera. She says in Chinese: 你好呀，今天也是元气满满的一天. Warm lamp light. No subtitles, no text overlay, no watermark.
```

## 从结果得出的结论
1. **定妆图里只能有一个主体。** Jolly 图里有前景小兽和背景水母，两次生成各挑了一个。
2. **文字和图必须一致。** A 的文字写 “Jellyfish… fluffy head”，图里的主角却是白毛小兽，文字和图片互相拉扯。
3. **参考图很可能被当成首帧。** A2 的开头就是参考图原画面，输出比例也跟着参考图走。所以每镜应该先做一张“首帧图”：角色在本镜场景里、比例就是成片画幅。
4. **否定句不保险。** 写了 “No subtitles”，A1 照样出了字幕。每镜都要查字幕，字幕需求放到剪辑时压。
5. **单人正面说一句短中文是可行的**（B），但声音要用户亲自听。

## Muse 自述的能力（经验，未全部验证）
- 时长固定约10秒，不能指定；分辨率约720p、24fps。
- 没有画幅参数、首尾帧参数、角色锁定功能；可以传多张参考图（用过4张）。
- 可以从上一条视频抽一帧，当作图片传给下一条续接（《云海仙境》用过，两帧 SSIM 0.888）。
- 同一会话可以续上下文（`resume_from_snapshot_id`），新会话要重新传图。
- 声音和画面一起生成，不能传入音频；不能锁定声线，换一条视频声音就变；有 TTS，可以先出静音画面再配音，但口型对不上。
- 描述用英文更稳，台词保留中文；提示词一两百字为宜，太长时后面的细节先丢。
- 时间码不会按秒执行，只当顺序参考。
- 每镜经验上限是2个动作、1种运镜。
- 剪辑用 ffmpeg：取中间一段、0.5秒交叉淡化、首尾淡入淡出；可以加 CC 授权音乐、压中文字幕、导出 mp4。
- 可以并行开子任务，每个任务一条。
- 血腥暴力容易被拒，被拒时不给原因。

## 下一轮要测
|编号|测什么|怎么做|看什么|
|---|---|---|---|
|V1|首帧图能不能控制画幅|用单主体定妆图生成一张9:16首帧图，再用它生成视频|输出是不是竖屏|
|V2|首帧图流程能不能锁人|同一张单主体定妆图 → 两个场景各做一张首帧图 → 各生成一条视频|两条主角是否一致|
|V3|原生中文读得对不对|用户亲自听演示B|15个字读对几个，嘴型是否同步|
|V4|同时传定妆图和上一镜抽帧时，比例跟哪张|两张图比例不同，一起传|输出比例|
|V5|肯定句能不能挡住字幕|A1原样，把 “No text, no subtitles” 换成 “clean image without any text”|还有没有字幕|
