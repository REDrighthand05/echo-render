#!/usr/bin/env python3
"""MUS demo — a fully synthetic scene, rendered entirely on CPU.

Builds a colourful point cube, a glowing helix and a ground grid from
plain numpy arrays, adds wireframe cube edges, and renders one frame
to ``docs/demo.png`` with :func:`mus_render.render_frame`.
No input files, no GPU, no browser.

Run from the repository root (works whether or not mus-render is
pip-installed)::

    python examples/render_demo.py
"""
import sys
from pathlib import Path

import numpy as np

# Make the in-repo package importable when mus-render is not installed.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mus_render import render_frame  # noqa: E402


def look_at(eye, target, focal=950.0, width=1280, height=720):
    """Build a mus_render camera dict: pinhole, world -> camera."""
    eye = np.asarray(eye, dtype=np.float64)
    fwd = np.asarray(target, dtype=np.float64) - eye
    fwd /= np.linalg.norm(fwd)
    up = np.array([0.0, 1.0, 0.0])
    right = np.cross(up, fwd)
    right /= np.linalg.norm(right)
    down = np.cross(right, fwd)
    R = np.stack([right, down, fwd])
    t = -R @ eye
    K = np.array([[focal, 0.0, width / 2.0],
                  [0.0, focal, height / 2.0],
                  [0.0, 0.0, 1.0]])
    return {"K": K, "R": R, "t": t}


def point_cube(half=1.0, n=26):
    """Points on the six faces of a cube; colour encodes position."""
    g = np.linspace(-half, half, n)
    faces = []
    for axis in range(3):
        for side in (-half, half):
            a, b = np.meshgrid(g, g)
            pts = np.empty((n * n, 3), dtype=np.float32)
            others = [i for i in range(3) if i != axis]
            pts[:, others[0]] = a.ravel()
            pts[:, others[1]] = b.ravel()
            pts[:, axis] = side
            faces.append(pts)
    xyz = np.concatenate(faces)
    rgb = ((xyz / (2.0 * half) + 0.5) * 255).astype(np.uint8)
    return xyz, rgb


def helix(turns=2.0, count=2600, radius=1.9):
    """A vertical helix of points with a cycling vivid colour."""
    t = np.linspace(0.0, turns * 2.0 * np.pi, count)
    xyz = np.stack([radius * np.cos(t),
                    np.linspace(-1.35, 1.35, count),
                    radius * np.sin(t)], axis=1).astype(np.float32)
    phase = t * 1.5
    rgb = np.stack([0.5 + 0.5 * np.sin(phase),
                    0.5 + 0.5 * np.sin(phase + 2.094),
                    0.5 + 0.5 * np.sin(phase + 4.189)], axis=1)
    return xyz, (rgb * 255).astype(np.uint8)


def ground_grid(half=3.4, n=25, y=-1.7):
    """A dim flat grid of points under the scene."""
    g = np.linspace(-half, half, n)
    a, b = np.meshgrid(g, g)
    xyz = np.stack([a.ravel(), np.full(n * n, y), b.ravel()],
                   axis=1).astype(np.float32)
    rgb = np.tile(np.array([[70, 85, 110]], dtype=np.uint8), (n * n, 1))
    return xyz, rgb


def cube_edges(half=1.0):
    """The 12 edges of the cube as (12, 2, 3) line segments."""
    c = np.array([[x, y, z] for x in (-half, half)
                  for y in (-half, half)
                  for z in (-half, half)], dtype=np.float32)
    edges = []
    for i in range(8):
        for j in range(i + 1, 8):
            if np.count_nonzero(c[i] != c[j]) == 1:
                edges.append([c[i], c[j]])
    return np.asarray(edges, dtype=np.float32)


def main():
    cube_xyz, cube_rgb = point_cube()
    helix_xyz, helix_rgb = helix()
    grid_xyz, grid_rgb = ground_grid()
    xyz = np.concatenate([cube_xyz, helix_xyz, grid_xyz])
    rgb = np.concatenate([cube_rgb, helix_rgb, grid_rgb])
    lines = cube_edges()
    lines_rgb = np.tile(np.array([[120, 190, 255]], dtype=np.uint8),
                        (lines.shape[0], 1))

    camera = look_at(eye=(4.4, 2.8, 5.4), target=(0.0, -0.1, 0.0))
    img = render_frame(xyz, rgb, lines, lines_rgb, camera=camera,
                       width=1280, height=720,
                       point_radius_px=2.2, glow_strength=0.55)

    from PIL import Image
    out = Path(__file__).resolve().parent.parent / "docs" / "demo.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(out)
    print(f"rendered {xyz.shape[0]} points + {lines.shape[0]} lines "
          f"-> {out}")


if __name__ == "__main__":
    main()
