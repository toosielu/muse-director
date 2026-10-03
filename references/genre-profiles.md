# 可选题材知识

根据实际作品选择本轮相关项；用户明确要求 > 已选用角色/剧本 > 题材建议 > 通用默认。题材只提供创作、美术与检查知识，不另调生成器、不引入其他模型、不要求必装子Skill或改变全片自主交付。

| 题材标识 | 角色卡 `genre_ext` 可用字段 | 镜头与检查重点 |
|---|---|---|
| `general` 通用 | 按实际项目保留 | 因果、必要动作、身份、空间、声音与剪辑 |
| `healing-ip` 治愈动画/IP | palette、proportions、face_rules、signature_props、texture | 用小目标和可见变化形成温情结果；统一比例、线条与标志物，环境保持风格；动作与停顿有节奏，不用静图替代必要行为 |
| `beauty-oncamera` 写实人物出镜/POV | face_shape、hairstyle、makeup、costume、lighting、camera_distance、skin_target | 主体已采用年龄/肤色与自然纹理；用表演和视线变化支撑镜头，避免过脏显老或塑料磨皮；裁切/皮肤/服装对照母版，非用户要求不增加触屏动作 |
| `guofeng-live` 写实古风 | era_or_fantasy、costume、hairstyle、ornaments、props、modern_elements_policy | 明确写实时代还是幻想混搭；服装结构、饰物、道具和空间一致；仅在采用设定排除现代元素时检查穿帮，不把具体朝代样式当统一历史事实 |

画幅按用途和用户要求选；竖屏时关注面部/关键动作/道具是否在构图与字幕可用区内，横屏时按其空间调度。不固定9:16、二头身、肤色、朝代或配色。古风服饰史不确定且项目需要精确性时查权威资料，不凭题材默认猜测。

可用已有题材Skill或外部建议补充 `defaults/card_ext/storyboard_patterns/prompt_fragments/pre_checks/post_checks/assembly/risks/unverified`，每个检查写观察依据和具体返修方式。只传本轮必要的简报、卡片、镜头和QA，不要求固定API或所有字段齐全。

中文/英文、分时段写法、参考组合、否定/肯定约束、原生声/后期声、转场和snapshot效果均是待比较方法，不能宣称某一默认保证成功。不存在的题材包、检查脚本或真实调用结果不得写成已安装/已通过。
