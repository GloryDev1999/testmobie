#!/usr/bin/env python3
"""
Headless Blender 3D & Animation MCP Server for AGY CLI.
Provides zero-cost 3D modeling, rigging, animation, multi-view visual preview,
glTF/GLB inspection, optimization, and batch generation (>100 models).
"""

from __future__ import annotations
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from PIL import Image, ImageDraw

mcp = FastMCP("blender_3d")

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _run_blender_python(script_content: str, extra_args: list[str] | None = None, timeout: int = 180) -> dict[str, Any]:
    """Execute a Python script inside headless Blender (with xvfb fallback for OpenGL renders)."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(script_content)
        tmp_path = tmp.name

    try:
        cmd = ["blender", "--background", "--factory-startup", "--python-exit-code", "1", "--python", tmp_path]
        if extra_args:
            cmd.append("--")
            cmd.extend(extra_args)
        if shutil.which("xvfb-run"):
            cmd = ["xvfb-run", "-a", *cmd]

        env = os.environ.copy()
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{TEMPLATES_DIR}:{existing_pp}" if existing_pp else str(TEMPLATES_DIR)

        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:] if proc.stdout else "",
            "stderr": proc.stderr[-4000:] if proc.stderr else "",
        }
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


@mcp.tool()
def blender_execute_script(
    code: str,
    export_glb_path: str = "",
    save_blend_path: str = "",
    render_preview_path: str = "",
) -> dict[str, Any]:
    """
    Execute Blender Python (bpy) code to model, rig, and animate 3D assets in headless mode.
    `import rig_and_anim_lib` is available automatically in the script scope.
    Optionally exports .glb, saves .blend, and renders a 4-view preview image (.png).
    """
    footer_lines = ["\nimport bpy, os"]
    if save_blend_path:
        Path(save_blend_path).parent.mkdir(parents=True, exist_ok=True)
        footer_lines.append(f"bpy.ops.wm.save_as_mainfile(filepath={save_blend_path!r})")
    if export_glb_path:
        Path(export_glb_path).parent.mkdir(parents=True, exist_ok=True)
        footer_lines.append(
            f"bpy.ops.export_scene.gltf(filepath={export_glb_path!r}, export_format='GLB', export_animations=True, export_nla_strips=True)"
        )

    full_code = code + "\n" + "\n".join(footer_lines) + "\n"
    res = _run_blender_python(full_code)

    preview_result = None
    if render_preview_path and (export_glb_path or save_blend_path):
        src = save_blend_path if save_blend_path else export_glb_path
        if os.path.exists(src):
            preview_result = blender_render_multiview(src, render_preview_path)

    return {
        "success": res["returncode"] == 0,
        "export_glb_path": export_glb_path if export_glb_path and os.path.exists(export_glb_path) else None,
        "save_blend_path": save_blend_path if save_blend_path and os.path.exists(save_blend_path) else None,
        "render_preview": preview_result,
        "stdout": res["stdout"],
        "stderr": res["stderr"],
    }


@mcp.tool()
def blender_render_multiview(input_model_path: str, output_image_path: str, resolution: int = 512) -> dict[str, Any]:
    """
    Render a 2x2 multi-angle preview sheet (Front, Side, Top, Isometric) of any .glb, .gltf, or .blend file
    so the AI agent can visually inspect proportions, colors, and geometry via read_file.
    """
    Path(output_image_path).parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = tempfile.mkdtemp(prefix="blender_views_")

    render_script = f"""
import bpy, math, os
from mathutils import Vector

inp = {input_model_path!r}
out_dir = {tmp_dir!r}
res = {int(resolution)}

if inp.endswith('.blend'):
    bpy.ops.wm.open_mainfile(filepath=inp)
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=inp)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = res
scene.render.resolution_y = res
scene.render.film_transparent = False

if not scene.world:
    scene.world = bpy.data.worlds.new("PreviewWorld")
scene.world.use_nodes = True
bg = scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.14, 0.15, 0.18, 1.0)
    bg.inputs[1].default_value = 1.2

# Compute bounding box of all meshes
mins = Vector((1e9, 1e9, 1e9))
maxs = Vector((-1e9, -1e9, -1e9))
has_mesh = False
for obj in scene.objects:
    if obj.type == 'MESH':
        has_mesh = True
        for corner in obj.bound_box:
            w = obj.matrix_world @ Vector(corner)
            mins.x, mins.y, mins.z = min(mins.x, w.x), min(mins.y, w.y), min(mins.z, w.z)
            maxs.x, maxs.y, maxs.z = max(maxs.x, w.x), max(maxs.y, w.y), max(maxs.z, w.z)

center = (mins + maxs) * 0.5 if has_mesh else Vector((0, 0, 0.8))
size = max((maxs - mins).length, 1.0) if has_mesh else 2.5
dist = size * 1.65

# Studio lights
for lname, loc, energy in [
    ("KeyLight", (dist, -dist, dist * 1.2), 4.0),
    ("FillLight", (-dist, -dist * 0.6, dist * 0.7), 2.0),
    ("RimLight", (0, dist, dist), 2.5),
]:
    ldata = bpy.data.lights.new(name=lname, type='SUN')
    ldata.energy = energy
    lobj = bpy.data.objects.new(name=lname, object_data=ldata)
    scene.collection.objects.link(lobj)
    lobj.location = center + Vector(loc)
    direction = center - lobj.location
    lobj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

cam_data = bpy.data.cameras.new("PreviewCam")
cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

views = {{
    "front": Vector((0, -dist, dist * 0.15)),
    "side": Vector((dist, 0, dist * 0.15)),
    "top": Vector((0.01, -0.01, dist * 1.2)),
    "iso": Vector((dist * 0.75, -dist * 0.75, dist * 0.65)),
}}

for vname, offset in views.items():
    cam_obj.location = center + offset
    direction = center - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = os.path.join(out_dir, f"{{vname}}.png")
    bpy.ops.render.render(write_still=True)
"""
    res = _run_blender_python(render_script)
    try:
        grid = Image.new("RGB", (resolution * 2, resolution * 2), (30, 32, 38))
        positions = [("front", 0, 0), ("side", resolution, 0), ("top", 0, resolution), ("iso", resolution, resolution)]
        draw = ImageDraw.Draw(grid)
        for vname, x, y in positions:
            vpath = os.path.join(tmp_dir, f"{vname}.png")
            if os.path.exists(vpath):
                img = Image.open(vpath).convert("RGB")
                grid.paste(img, (x, y))
                draw.text((x + 12, y + 12), vname.upper(), fill=(255, 230, 100))
        grid.save(output_image_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return {
        "success": os.path.exists(output_image_path),
        "output_image_path": output_image_path,
        "returncode": res["returncode"],
    }


@mcp.tool()
def blender_inspect_model(file_path: str) -> dict[str, Any]:
    """Inspect a .glb, .gltf, or .blend file and return mesh stats, bones, materials, and animations."""
    inspect_script = f"""
import bpy, json
fp = {file_path!r}
if fp.endswith('.blend'):
    bpy.ops.wm.open_mainfile(filepath=fp)
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=fp)

meshes = []
total_verts = 0
total_faces = 0
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH':
        v = len(obj.data.vertices)
        p = len(obj.data.polygons)
        total_verts += v
        total_faces += p
        meshes.append({{"name": obj.name, "vertices": v, "polygons": p}})

bones = []
for arm in bpy.data.armatures:
    bones.extend([b.name for b in arm.bones])

actions = []
for act in bpy.data.actions:
    actions.append({{"name": act.name, "frame_range": [float(act.frame_range[0]), float(act.frame_range[1])]}})

info = {{
    "file": fp,
    "file_size_kb": round(os.path.getsize(fp) / 1024, 2) if os.path.exists(fp) else 0,
    "mesh_count": len(meshes),
    "total_vertices": total_verts,
    "total_polygons": total_faces,
    "meshes": meshes,
    "bone_count": len(bones),
    "bones": bones,
    "materials": [m.name for m in bpy.data.materials],
    "animations": actions,
}}
print("JSON_INSPECT_START:" + json.dumps(info) + ":JSON_INSPECT_END")
"""
    res = _run_blender_python("import os\n" + inspect_script)
    stdout = res["stdout"]
    if "JSON_INSPECT_START:" in stdout and ":JSON_INSPECT_END" in stdout:
        raw = stdout.split("JSON_INSPECT_START:")[1].split(":JSON_INSPECT_END")[0]
        return json.loads(raw)
    return {"error": "Failed to inspect model", "stdout": stdout, "stderr": res["stderr"]}


@mcp.tool()
def blender_optimize_glb(input_path: str, output_path: str = "") -> dict[str, Any]:
    """Optimize a .glb file or directory of .glb files using @gltf-transform/cli (dedup, prune, weld)."""
    p = Path(input_path)
    if p.is_dir():
        files = sorted(p.glob("*.glb"))
        optimized = []
        for f in files:
            before_kb = f.stat().st_size / 1024
            subprocess.run(["gltf-transform", "optimize", str(f), str(f), "--compress", "quantize"], check=False, capture_output=True)
            after_kb = f.stat().st_size / 1024
            optimized.append({"file": f.name, "before_kb": round(before_kb, 1), "after_kb": round(after_kb, 1)})
        return {"optimized_count": len(optimized), "files": optimized}
    else:
        target = output_path or input_path
        before_kb = p.stat().st_size / 1024 if p.exists() else 0
        proc = subprocess.run(
            ["gltf-transform", "optimize", str(p), str(target), "--compress", "quantize"],
            capture_output=True,
            text=True,
            check=False,
        )
        after_kb = Path(target).stat().st_size / 1024 if Path(target).exists() else 0
        return {
            "success": proc.returncode == 0,
            "output_path": str(target),
            "before_kb": round(before_kb, 1),
            "after_kb": round(after_kb, 1),
        }


@mcp.tool()
def blender_batch_generate(
    generator_script_path: str,
    count: int,
    output_dir: str,
    seed: int = 42,
    optimize: bool = True,
) -> dict[str, Any]:
    """
    Run a parametric Blender generator script in a single headless process to generate
    `count` (e.g. 10 to 100+) 3D .glb models with animations at 0 LLM token cost.
    The generator script receives CLI args: `-- <output_dir> <count> <seed>`.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    code = Path(generator_script_path).read_text(encoding="utf-8")
    res = _run_blender_python(code, extra_args=[str(output_dir), str(count), str(seed)], timeout=600)
    opt_summary = None
    if optimize and res["returncode"] == 0:
        opt_summary = blender_optimize_glb(output_dir)
    glb_files = sorted(str(p) for p in Path(output_dir).glob("*.glb"))
    return {
        "success": res["returncode"] == 0,
        "generated_count": len(glb_files),
        "output_dir": output_dir,
        "sample_files": glb_files[:10],
        "optimization": opt_summary,
        "stdout": res["stdout"],
        "stderr": res["stderr"],
    }


if __name__ == "__main__":
    mcp.run()
