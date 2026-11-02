# Echo Render — ECHO 配套高性能渲染算子

<div align="center">

![License](https://img.shields.io/badge/License-MIT-0e75b6?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-%E2%89%A53.10-38bdf8?style=for-the-badge&logo=python)
![GPU](https://img.shields.io/badge/GPU-%E4%B8%8D%E9%9C%80%E8%A6%81-2ea44f?style=for-the-badge)
[![Part of ECHO](https://img.shields.io/badge/Part_of-ECHO_%E5%9B%9E%E5%A3%B0-0e75b6?style=for-the-badge&logo=github)](https://github.com/REDrighthand05/echo4d)

</div>

**纯 CPU 的点云 / 线框渲染器。** 给它带颜色的 3D 点（可选线段）和一个针孔
相机，它直接算出一帧图像 —— 不需要 GPU，不需要浏览器，不需要图形 API。
底层只有 numpy + numba。

本算子为 [ECHO 回声](https://github.com/REDrighthand05/echo4d) 的配套组件，引擎代号 MUS。
Echo Render is the companion renderer for ECHO; engine codename MUS.
It is tailored to ECHO's data specs, and released standalone so anyone
can use it out of the box.

![demo](docs/demo.png)

*上图由 `examples/render_demo.py` 用纯合成数据（点立方体 + 螺旋 + 地面
网格 + 线框边）渲染，单帧，CPU。*

## 特性

- **纯 CPU**：numpy + numba 编译内核；投影并行（`prange`）。
- **确定性输出**：点按深度远→近的固定顺序（稳定排序）绘制，合成是累积
  缓冲的纯函数 —— 相同输入永远产生相同字节，与核心数无关。
- **只画给定的几何**：不估计、不投票、不平均几何。点是带辉光的圆盘 +
  不透明圆芯（画家序，近点赢得圆芯像素）；线段是 1px Xiaolin Wu 抗锯
  齿线，画在点之下。
- **开箱即用**：两个函数就是全部 API —— `render_frame`（单帧）和
  `render_sequence`（JSON 描述的批量渲染 → PNG 序列）。

## 安装

```bash
git clone https://github.com/REDrighthand05/echo-render
cd echo-render
pip install .
```

依赖：`numpy`、`numba>=0.58`、`Pillow`（仅 `render_sequence` 写 PNG 时
用），Python ≥ 3.10。

## 最小例子（数组进 → PNG 出）

```python
import numpy as np
from PIL import Image
from echo_render import render_frame

# A cube shell of points; colour encodes position.
g = np.linspace(-1, 1, 26)
faces = []
for axis in range(3):
    for side in (-1.0, 1.0):
        a, b = np.meshgrid(g, g)
        pts = np.empty((26 * 26, 3), dtype=np.float32)
        others = [i for i in range(3) if i != axis]
        pts[:, others[0]] = a.ravel()
        pts[:, others[1]] = b.ravel()
        pts[:, axis] = side
        faces.append(pts)
xyz = np.concatenate(faces)
rgb = ((xyz / 2.0 + 0.5) * 255).astype(np.uint8)

# Pinhole camera: Xc = R @ X + t, u = fx * Xc.x / Xc.z + cx, ...
eye = np.array([4.4, 2.8, 5.4])
fwd = -eye / np.linalg.norm(eye)          # look at the origin
right = np.cross([0.0, 1.0, 0.0], fwd); right /= np.linalg.norm(right)
down = np.cross(right, fwd)
R = np.stack([right, down, fwd])
camera = {"K": np.array([[950.0, 0, 640], [0, 950.0, 360], [0, 0, 1]]),
          "R": R, "t": -R @ eye}

img = render_frame(xyz, rgb, camera=camera)   # uint8 (720, 1280, 3)
Image.fromarray(img).save("frame.png")
```

完整示例（即顶部演示图的来源）在 `examples/render_demo.py`，
克隆后无需安装即可直接运行：

```bash
python examples/render_demo.py
```

## `render_frame` 参数表

```python
render_frame(points_xyz, points_rgb, lines_xyz=None, lines_rgb=None,
             camera=None, width=1280, height=720,
             point_radius_px=2.0, glow_strength=0.6,
             glow_radius_factor=2.5, background_rgb=(5, 7, 14),
             near=1e-4) -> uint8[H, W, 3]
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `points_xyz` | （必填） | `(N, 3)` 世界坐标点，float |
| `points_rgb` | （必填） | `(N, 3)` 颜色：uint8 0–255，或 float [0, 1]（自动缩放） |
| `lines_xyz` | `None` | `(M, 2, 3)` 线段端点，画在点之下；任一端点在近平面之后则整段跳过 |
| `lines_rgb` | `None` | `(M, 3)` 线段颜色；缺省为浅蓝 (96, 165, 250) |
| `camera` | （必填） | dict `{"K": (3,3), "R": (3,3), "t": (3,)}`，针孔内参 + 世界→相机旋转/平移 |
| `width`, `height` | `1280, 720` | 输出图像尺寸（像素） |
| `point_radius_px` | `2.0` | 点的不透明圆芯半径（像素，下限 0.5，保证每个可见点都落像） |
| `glow_strength` | `0.6` | 辉光强度（加色叠加，权重 `glow_strength * (1 - d/r)²`）；0 关闭辉光 |
| `glow_radius_factor` | `2.5` | 辉光盘半径 = 圆芯半径 × 该系数 |
| `background_rgb` | `(5, 7, 14)` | 背景色 0–255 |
| `near` | `1e-4` | 相机空间 z ≤ near 的点被裁剪 |

相机约定：`Xc = R @ X + t`，`u = fx·Xc.x/Xc.z + cx`，
`v = fy·Xc.y/Xc.z + cy`，其中 `fx, cx` 取 `K[0,0], K[0,2]`，
`fy, cy` 取 `K[1,1], K[1,2]`。

## `render_sequence`

批量渲染：一个 JSON 文件描述全局参数（同上，可逐帧覆盖）与帧列表，
每帧给出 `.npy` 点/颜色/线段文件、相机与输出 PNG 名；还支持
`point_count`（只画前 K 个点 —— 渐进显现）与 `point_indices`
（只画指定点）。相对路径以 spec 文件所在目录为基准。返回写出的
PNG 路径列表。

## 性能（实测，不吹）

在一台 4 核共享 VM 上（有其他任务并行，数字是一个区间而非单点）：
208,666 个点、辉光开启时，1280×720 约 **112–278 ms/帧**，
1920×1080 约 **178–316 ms/帧**；耗时随实际绘制的点数缩放。
作为对照，同等内容的浏览器 WebGL 截屏路线在同一台机器上端到端
要慢一个数量级以上，且不保证逐帧字节一致。

## 诚实说明

- **只有 CPU 路线**，没有 GPU 后端；这正是它的定位 —— 在没有显卡、
  或不想引入图形栈的机器上稳定出图。
- 它**只渲染你给的几何**：不补洞、不平滑、不生成任何输入里没有的
  东西。给什么，画什么。
- 点的泼溅（splat）是刻意单线程顺序执行的 —— 固定绘制顺序是逐
  字节确定性的代价与来源；投影部分是并行的。

## License

MIT — 见 [LICENSE](LICENSE)。

---

# Echo Render — a fast CPU point-cloud & wireframe renderer

**A pure-CPU point-cloud & wireframe renderer.** Feed it coloured 3D
points (and optional line segments) plus a pinhole camera, and it
computes a frame directly — no GPU, no browser, no graphics API.
Built on numpy + numba only.

## Features

- **Pure CPU**: numpy + numba kernels; projection is parallel
  (`prange`).
- **Bit-deterministic**: points are splatted in one fixed far-to-near
  order (stable sort); compositing is a pure function of the
  accumulation buffer. Same inputs → same bytes, on any core count.
- **Draws exactly the geometry given**: no estimation, no voting, no
  geometry averaging. Points are glow discs with an opaque core
  (painter's order — the nearest point wins its core pixels); lines
  are 1px Xiaolin Wu anti-aliased segments drawn beneath the points.
- **Out of the box**: the whole API is two functions —
  `render_frame` (one frame) and `render_sequence` (a JSON-described
  batch rendered to PNGs, with progressive-reveal support).

## Install

```bash
git clone https://github.com/REDrighthand05/echo-render
cd echo-render
pip install .
```

Dependencies: `numpy`, `numba>=0.58`, `Pillow` (only used by
`render_sequence` for PNG output); Python ≥ 3.10.

## Minimal example

See the Chinese section above for a complete arrays-in → PNG-out
example, and `examples/render_demo.py` (the source of the demo image
at the top) — it runs from a fresh clone, no install needed:

```bash
python examples/render_demo.py
```

## API

```python
render_frame(points_xyz, points_rgb, lines_xyz=None, lines_rgb=None,
             camera=None, width=1280, height=720,
             point_radius_px=2.0, glow_strength=0.6,
             glow_radius_factor=2.5, background_rgb=(5, 7, 14),
             near=1e-4) -> uint8[H, W, 3]
```

- `points_xyz`: `(N, 3)` world-space points (float).
- `points_rgb`: `(N, 3)` uint8 colours 0–255, or floats in [0, 1].
- `lines_xyz`: optional `(M, 2, 3)` segment endpoints, drawn under
  the points; a segment is skipped if either endpoint is behind the
  near plane.
- `lines_rgb`: optional `(M, 3)`; default light blue (96, 165, 250).
- `camera`: dict `{"K": (3,3), "R": (3,3), "t": (3,)}` — pinhole
  intrinsics and world→camera rotation/translation. Required.
  Convention: `Xc = R @ X + t`, `u = fx·Xc.x/Xc.z + cx`,
  `v = fy·Xc.y/Xc.z + cy`.
- `point_radius_px`: radius of each point's opaque core (≥ 0.5).
- `glow_strength`: additive halo scale, weight
  `glow_strength * (1 - d/r)²`; 0 disables the halo.
- `glow_radius_factor`: halo radius = core radius × this.
- `background_rgb`: background colour (default `(5, 7, 14)`).
- `near`: points with camera-space z ≤ near are culled.

`render_sequence(spec_json_path, out_dir)` renders a JSON-described
batch (global params + per-frame `.npy` inputs, cameras, per-frame
overrides, `point_count` / `point_indices` for progressive reveal)
and returns the list of written PNG paths.

## Performance (measured, honestly)

On a 4-core shared VM (other jobs running — treat as a band, not a
point): the full 208,666-point cloud with glow renders at roughly
**112–278 ms/frame at 1280×720** and **178–316 ms/frame at
1920×1080**. Cost scales with the number of points actually drawn.

## Honest notes

- **CPU only** — there is no GPU backend, by design: Echo Render targets
  machines without a GPU, or pipelines that don't want a graphics
  stack, and must be reproducible there.
- It renders **only** the geometry you pass in: no hole filling, no
  smoothing, nothing invented.
- Point splatting is deliberately sequential in a fixed depth order —
  that fixed order is what buys bit-determinism; projection is the
  parallel part.

## License

MIT — see [LICENSE](LICENSE).
