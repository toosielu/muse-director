# 示例：一句话 → 30秒故事板

教学示例，还没有拿去生成。展示[主文件](../muse-idea-to-short.md)第1–4节怎么落地。

## 用户说
> 做一条30秒竖屏治愈动画：蓝外套小兔把迷路的萤火虫带回灯笼。

## 整理成故事板
```
片名：回家的光｜30秒｜9:16｜温暖手绘二维，平涂，柔和蓝紫夜色配暖黄灯光
角色锚点：
  小兔：手绘平涂的白色小兔，两头身，两只直立长耳，蓝色短外套，胸前一颗黄纽扣
  （英文固定版）A hand-drawn white bunny, two heads tall, two upright long ears, short blue jacket, one yellow button on the chest.
  萤火虫：拇指大小的卡通萤火虫，圆身体，尾部发暖黄光，一对透明小翅膀
场景锚点：
  森林小路：夜晚，石板小路分成两条岔路，右侧木栅栏，栅栏上挂一盏圆形黄纸灯笼，月光从左上方照下
说话方式：无对白，轻柔钢琴加虫鸣，后期加
```

|镜号|取用秒数|地点|画面一句话|景别|台词|和上一镜怎么接|
|---|---|---|---|---|---|---|
|1|8|森林小路|萤火虫在岔路口飞来飞去找不到方向，光一闪一闪变暗|远景→缓慢推近|无|开场|
|2|7|森林小路|小兔从右边走进画面，蹲下，抬起耳朵看着萤火虫|中景|无|换景别：远→中|
|3|8|森林小路|小兔摘下栅栏上的灯笼举高，萤火虫跟着光飞过来|中景，侧面|无|换角度：正→侧|
|4|7|森林小路|萤火虫飞进灯笼，灯笼亮起来；小兔抱着灯笼笑|近景|无|换景别：中→近，结尾主角看得清|

同时附上：小兔定妆图、萤火虫定妆图。两张图各自只画一个角色，纯色背景，全身正面。

## 第2镜怎么生成
**先做首帧图**（以小兔定妆图为参考，比例9:16）：
```
Warm hand-drawn 2D, flat colors, soft blue-purple night with warm yellow light. Vertical 9:16.
A hand-drawn white bunny, two heads tall, two upright long ears, short blue jacket, one yellow button on the chest.
Night forest path splitting into two stone trails, wooden fence on the right with a round yellow paper lantern, moonlight from the upper left.
The bunny stands at the right edge of the frame, about to step in. Medium shot.
```
确认首帧图里的小兔和定妆图一致、比例是竖屏，再**用首帧图生成视频**。画风句和锚点句都要带上，只写动作时画风容易漂：
```
Warm hand-drawn 2D, flat colors, soft blue-purple night with warm yellow light.
A hand-drawn white bunny, two heads tall, two upright long ears, short blue jacket, one yellow button on the chest.
The bunny walks slowly to the fork, crouches down, and raises both ears, curiously watching a flickering firefly in front of it. Medium shot, camera gently follows.
Sound: crickets and soft footsteps. Clean image without any text.
（参考图：第2镜首帧图）
```
锚点句放在最前面，和图里的样子一致；其余部分由 Muse 用自己擅长的方式写。

## 为什么这样拆
- 4镜×约7.5秒=30秒，每镜都是一个完整的小动作。
- 相邻镜头都换了景别或角度，剪起来不会跳。
- 全程一个地点，不用过渡镜。
- 最后一镜是近景，主角和结局都看得清。
