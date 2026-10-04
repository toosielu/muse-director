# 后台工具

用户只需把[主文件](../muse-idea-to-short.md)发给 Muse。本目录给维护者和助手用，不生成视频，也不调用 Muse。

## 量视频的画幅和时长

需要本机装有 FFmpeg（`ffprobe`）。下载 Muse 的成片后运行：

```sh
python tools/u0_check.py downloaded.mp4 --target-aspect 0.5625 --min-seconds 6 --max-seconds 10 --min-short-side 720
```

`0.5625` 是竖屏9:16（宽÷高），横屏16:9写 `1.7778`。输出 JSON：画幅或时长不对是 FAIL（返回码2）；短边偏小或疑似中间有硬切是 WARN（返回码0）；工具没跑成是 UNVERIFIED（返回码3）。疑似硬切也可能是闪光或场景变化，要自己看片确认。工具不会改动视频。

## 包检查

```sh
python -m unittest discover -s tools/tests -p "test_*.py"
python tools/check_package.py
```

`check_package.py` 检查必需文件、主文件的必备小节、本地链接和测试集是否齐全，并报告主文件长度，不设主文件字数上限。`drafts/` 只检查文件和链接，不把草稿当成制作规则。它只检查文字结构，不代表视频效果。
