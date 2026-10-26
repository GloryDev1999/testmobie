"""
High-Detail Stylized 3D Character Generator: ZEUS (God of Thunder) - V2 Refined
Matches the 6-panel turnaround reference sheet (/workspaces/testmobie/zues.png):
- Heroic muscular proportions, warm peach-tan skin, sculpted pectorals, abs & deltoids
- Flowing wavy silver-white hair (top waves, side locks, cascading back curls)
- Full layered wavy beard, sweeping curled mustache, thick angled white eyebrows
- Golden laurel wreath crown with 6 overlapping angled golden leaves per side
- White Greek toga/chiton with diagonal chest sash, left-shoulder gold brooch, back cape, and gold-trimmed pleated kilt
- Golden waist belt with prominent central round gold medallion buckle & inner rim
- Golden forearm bracers with raised gold cuffs & brown leather Greek sandals
- Glowing cyan-blue zig-zag Lightning Bolt gripped directly in right fist
- Full Armature Rig + 4 Animations: Idle, Walk, Jump, ThunderStrike
- Includes a 6-panel Turnaround Sheet renderer matching /workspaces/testmobie/zues.png
"""

from __future__ import annotations
import math
import os
import shutil
import sys
import tempfile
import bpy
import bmesh
from mathutils import Vector
from PIL import Image, ImageDraw
import rig_and_anim_lib as lib


def add_subsurf_and_shade_smooth(obj: bpy.types.Object, levels: int = 1) -> None:
    if levels > 0:
        mod = obj.modifiers.new(name="Subsurf", type="SUBSURF")
        mod.levels = levels
        mod.render_levels = levels
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for poly in obj.data.polygons:
        poly.use_smooth = True


def create_box(
    name: str,
    loc: tuple[float, float, float],
    scale: tuple[float, float, float],
    rot_deg: tuple[float, float, float] = (0, 0, 0),
    bevel_width: float = 0.03,
    subsurf: int = 1,
    mat: bpy.types.Material | None = None,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    if bevel_width > 0:
        bev = obj.modifiers.new(name="Bevel", type="BEVEL")
        bev.width = bevel_width
        bev.segments = 2
        bpy.ops.object.modifier_apply(modifier=bev.name)
    add_subsurf_and_shade_smooth(obj, subsurf)
    if mat:
        lib.assign_material(obj, mat)
    return obj


def create_sphere(
    name: str,
    loc: tuple[float, float, float],
    scale: tuple[float, float, float],
    rot_deg: tuple[float, float, float] = (0, 0, 0),
    mat: bpy.types.Material | None = None,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=14, radius=1.0, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    if mat:
        lib.assign_material(obj, mat)
    return obj


def create_cylinder(
    name: str,
    loc: tuple[float, float, float],
    radius: float,
    depth: float,
    scale: tuple[float, float, float] = (1, 1, 1),
    rot_deg: tuple[float, float, float] = (0, 0, 0),
    vertices: int = 20,
    mat: bpy.types.Material | None = None,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bev = obj.modifiers.new(name="Bevel", type="BEVEL")
    bev.width = min(radius, depth) * 0.08
    bev.segments = 2
    bpy.ops.object.modifier_apply(modifier=bev.name)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    if mat:
        lib.assign_material(obj, mat)
    return obj


def create_lightning_bolt(name: str, mat_glow: bpy.types.Material) -> bpy.types.Object:
    """Create the jagged zig-zag glowing cyan-blue lightning bolt gripped directly in Zeus's right fist."""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)

    bm = bmesh.new()
    # Centered at (0, 0, 0) where the right fist grips it
    spine_pts = [
        (0.28, -0.62, 0.010),   # Bottom sharp tip pointing down-inward
        (0.06, -0.22, 0.055),   # Lower zig
        (0.18, -0.15, 0.048),   # Lower zag
        (-0.02, 0.02, 0.045),   # Grip handle at (0,0,0) inside fist
        (0.08, 0.08, 0.048),    # Upper zig
        (-0.14, 0.36, 0.058),   # Upper zag
        (-0.02, 0.42, 0.042),   # Top notch
        (-0.22, 0.78, 0.010),   # Top sharp tip
    ]

    rings = []
    for x, z, w in spine_pts:
        t = max(w * 0.55, 0.014)
        v1 = bm.verts.new((x - w, -t, z))
        v2 = bm.verts.new((x + w, -t, z))
        v3 = bm.verts.new((x + w, t, z))
        v4 = bm.verts.new((x - w, t, z))
        rings.append((v1, v2, v3, v4))

    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    for i in range(len(rings) - 1):
        r0 = rings[i]
        r1 = rings[i + 1]
        for j in range(4):
            jn = (j + 1) % 4
            bm.faces.new((r0[j], r0[jn], r1[jn], r1[j]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()

    # Placed directly inside Right Hand (-0.54, -0.09, 0.65) and angled diagonally like FRONT panel of zues.png
    obj.location = (-0.52, -0.12, 0.64)
    obj.rotation_euler = (math.radians(18), math.radians(16), math.radians(-10))
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.select_set(False)
    lib.assign_material(obj, mat_glow)
    return obj


def add_thunder_strike_animation(arm_obj: bpy.types.Object) -> None:
    """Add a 4th heroic animation: ThunderStrike (Zeus raises the lightning bolt and strikes!)."""
    act = bpy.data.actions.new(name="ThunderStrike")
    arm_obj.animation_data.action = act

    def reset_pose():
        for pb in arm_obj.pose.bones:
            pb.location = (0, 0, 0)
            pb.rotation_euler = (0, 0, 0)
            pb.scale = (1, 1, 1)

    keyframes = [
        (1, 0.0, 0.0, 0.0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        (10, 0.06, -0.18, 0.25, (-2.1, 0.0, -0.35), (0.4, 0.0, 0.45)),
        (16, -0.08, 0.28, -0.30, (1.1, 0.0, 0.15), (-0.5, 0.0, 0.30)),
        (24, -0.04, 0.12, -0.15, (0.6, 0.0, 0.10), (-0.2, 0.0, 0.20)),
        (32, 0.0, 0.0, 0.0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
    ]
    for f, hz, sp_x, sp_z, ar_r, ar_l in keyframes:
        reset_pose()
        arm_obj.pose.bones["Hips"].location = (0, 0, hz)
        arm_obj.pose.bones["Spine"].rotation_euler = (sp_x, 0, sp_z)
        arm_obj.pose.bones["Arm.R"].rotation_euler = ar_r
        arm_obj.pose.bones["Arm.L"].rotation_euler = ar_l
        for bname in ("Hips", "Spine", "Head", "Arm.L", "Arm.R", "Leg.L", "Leg.R"):
            pb = arm_obj.pose.bones[bname]
            pb.keyframe_insert(data_path="location", frame=f)
            pb.keyframe_insert(data_path="rotation_euler", frame=f)

    act.use_fake_user = True
    track = arm_obj.animation_data.nla_tracks.new()
    track.name = act.name
    strip = track.strips.new(act.name, 1, act)
    strip.name = act.name
    arm_obj.animation_data.action = None


def build_zeus(output_glb: str, output_blend: str = "") -> bpy.types.Object:
    lib.clear_scene()

    # Palette tuned to /workspaces/testmobie/zues.png
    mat_skin = lib.create_pbr_material("Zeus_Skin", (0.91, 0.62, 0.45, 1.0), metallic=0.0, roughness=0.52)
    mat_hair = lib.create_pbr_material("Zeus_WhiteHair", (0.93, 0.94, 0.97, 1.0), metallic=0.04, roughness=0.42)
    mat_toga = lib.create_pbr_material("Zeus_WhiteToga", (0.96, 0.94, 0.89, 1.0), metallic=0.0, roughness=0.60)
    mat_gold = lib.create_pbr_material("Zeus_Gold", (0.94, 0.70, 0.16, 1.0), metallic=0.75, roughness=0.26)
    mat_leather = lib.create_pbr_material("Zeus_SandalLeather", (0.40, 0.22, 0.10, 1.0), metallic=0.05, roughness=0.62)
    mat_eye_dark = lib.create_pbr_material("Zeus_Eyes", (0.10, 0.08, 0.07, 1.0), metallic=0.0, roughness=0.15)
    mat_lightning = lib.create_pbr_material(
        "Zeus_Lightning",
        (0.22, 0.82, 1.0, 1.0),
        metallic=0.0,
        roughness=0.1,
        emission_color=(0.20, 0.80, 1.0, 1.0),
        emission_strength=3.8,
    )

    arm_obj = lib.create_humanoid_rig(name="ZeusRig", scale=1.0)

    # 1. Muscular Torso, Pectorals, Back Lats & Toga Sash (Spine)
    torso = create_box("Torso_Upper", (0, 0, 1.06), (0.56, 0.34, 0.42), bevel_width=0.08, subsurf=1, mat=mat_skin)
    lib.parent_part_to_bone(torso, arm_obj, "Spine")

    for side in (-1, 1):
        pec = create_box(
            f"Pectoral_{side}",
            (side * 0.13, -0.155, 1.13),
            (0.23, 0.10, 0.16),
            bevel_width=0.05,
            subsurf=1,
            mat=mat_skin,
        )
        lib.parent_part_to_bone(pec, arm_obj, "Spine")

    sash_front = create_box(
        "Toga_ChestSash",
        (0.04, -0.155, 1.04),
        (0.25, 0.15, 0.56),
        rot_deg=(0, 27, 0),
        bevel_width=0.04,
        subsurf=1,
        mat=mat_toga,
    )
    lib.parent_part_to_bone(sash_front, arm_obj, "Spine")

    sash_back = create_box(
        "Toga_BackSash",
        (0.04, 0.15, 1.04),
        (0.27, 0.13, 0.56),
        rot_deg=(0, 24, 0),
        bevel_width=0.04,
        subsurf=1,
        mat=mat_toga,
    )
    lib.parent_part_to_bone(sash_back, arm_obj, "Spine")

    back_cape = create_box(
        "Toga_BackCape",
        (0.18, 0.21, 0.80),
        (0.28, 0.06, 0.74),
        rot_deg=(6, -6, 0),
        bevel_width=0.02,
        subsurf=1,
        mat=mat_toga,
    )
    lib.parent_part_to_bone(back_cape, arm_obj, "Spine")

    cape_gold_trim = create_box(
        "Gold_CapeTrim",
        (0.20, 0.23, 0.44),
        (0.28, 0.065, 0.05),
        rot_deg=(6, -6, 0),
        bevel_width=0.01,
        subsurf=1,
        mat=mat_gold,
    )
    lib.parent_part_to_bone(cape_gold_trim, arm_obj, "Spine")

    brooch = create_cylinder(
        "Gold_ShoulderBrooch",
        (0.20, -0.185, 1.24),
        radius=0.070,
        depth=0.045,
        rot_deg=(82, 0, -15),
        mat=mat_gold,
    )
    lib.parent_part_to_bone(brooch, arm_obj, "Spine")

    shoulder_strap = create_box(
        "Gold_ShoulderStrap",
        (0.27, 0.0, 1.28),
        (0.14, 0.30, 0.055),
        rot_deg=(0, -12, 0),
        bevel_width=0.015,
        subsurf=1,
        mat=mat_gold,
    )
    lib.parent_part_to_bone(shoulder_strap, arm_obj, "Spine")

    # 2. Waist Belt, Medallion Buckle & Pleated Toga Kilt (Hips)
    belt = create_cylinder(
        "Gold_WaistBelt",
        (0, 0, 0.80),
        radius=0.28,
        depth=0.105,
        scale=(1.06, 0.73, 1.0),
        mat=mat_gold,
    )
    lib.parent_part_to_bone(belt, arm_obj, "Hips")

    buckle = create_cylinder(
        "Gold_BeltMedallion",
        (0, -0.215, 0.80),
        radius=0.082,
        depth=0.055,
        rot_deg=(90, 0, 0),
        mat=mat_gold,
    )
    lib.parent_part_to_bone(buckle, arm_obj, "Hips")

    kilt_main = create_cylinder(
        "Toga_KiltMain",
        (0, 0, 0.56),
        radius=0.295,
        depth=0.42,
        scale=(1.06, 0.76, 1.0),
        mat=mat_toga,
    )
    lib.parent_part_to_bone(kilt_main, arm_obj, "Hips")

    kilt_trim = create_cylinder(
        "Gold_KiltHemTrim",
        (0, 0, 0.36),
        radius=0.305,
        depth=0.048,
        scale=(1.07, 0.77, 1.0),
        mat=mat_gold,
    )
    lib.parent_part_to_bone(kilt_trim, arm_obj, "Hips")

    flap = create_box("Toga_CenterFlap", (0, -0.22, 0.56), (0.15, 0.045, 0.40), bevel_width=0.01, subsurf=1, mat=mat_toga)
    lib.parent_part_to_bone(flap, arm_obj, "Hips")

    flap_trim = create_box("Gold_CenterFlapTrim", (0, -0.225, 0.37), (0.155, 0.05, 0.04), bevel_width=0.008, subsurf=1, mat=mat_gold)
    lib.parent_part_to_bone(flap_trim, arm_obj, "Hips")

    # 3. Head, Hair, Layered Beard, Curled Mustache & Golden Laurel Wreath (Head)
    head_base = create_sphere("Zeus_Head", (0, -0.02, 1.54), (0.23, 0.22, 0.26), mat=mat_skin)
    lib.parent_part_to_bone(head_base, arm_obj, "Head")

    nose = create_box("Zeus_Nose", (0, -0.24, 1.53), (0.055, 0.075, 0.095), rot_deg=(10, 0, 0), bevel_width=0.02, mat=mat_skin)
    lib.parent_part_to_bone(nose, arm_obj, "Head")

    for side in (-1, 1):
        ear = create_sphere(f"Zeus_Ear_{side}", (side * 0.22, -0.01, 1.53), (0.04, 0.06, 0.08), mat=mat_skin)
        lib.parent_part_to_bone(ear, arm_obj, "Head")

        eye = create_sphere(f"Zeus_Eye_{side}", (side * 0.075, -0.215, 1.565), (0.026, 0.020, 0.028), mat=mat_eye_dark)
        lib.parent_part_to_bone(eye, arm_obj, "Head")

        brow = create_box(
            f"Zeus_Brow_{side}",
            (side * 0.082, -0.228, 1.615),
            (0.095, 0.045, 0.034),
            rot_deg=(0, side * -10, 0),
            bevel_width=0.01,
            mat=mat_hair,
        )
        lib.parent_part_to_bone(brow, arm_obj, "Head")

    # Full Sculpted White Beard & Mustache
    beard_main = create_sphere("Zeus_BeardMain", (0, -0.145, 1.34), (0.23, 0.18, 0.22), mat=mat_hair)
    lib.parent_part_to_bone(beard_main, arm_obj, "Head")

    beard_tip = create_sphere("Zeus_BeardTip", (0, -0.175, 1.20), (0.14, 0.12, 0.14), mat=mat_hair)
    lib.parent_part_to_bone(beard_tip, arm_obj, "Head")

    for side in (-1, 1):
        beard_side = create_sphere(f"Zeus_BeardSide_{side}", (side * 0.15, -0.115, 1.38), (0.115, 0.125, 0.16), mat=mat_hair)
        lib.parent_part_to_bone(beard_side, arm_obj, "Head")

        beard_lock = create_sphere(f"Zeus_BeardLock_{side}", (side * 0.09, -0.165, 1.25), (0.085, 0.095, 0.12), mat=mat_hair)
        lib.parent_part_to_bone(beard_lock, arm_obj, "Head")

        stache = create_box(
            f"Zeus_Mustache_{side}",
            (side * 0.09, -0.24, 1.465),
            (0.15, 0.06, 0.055),
            rot_deg=(0, side * 18, side * -12),
            bevel_width=0.02,
            mat=mat_hair,
        )
        lib.parent_part_to_bone(stache, arm_obj, "Head")

    # Voluminous Wavy White Hair (Crown Waves, Side Locks, Back Mane)
    hair_top = create_sphere("Zeus_HairTop", (0, 0.02, 1.67), (0.255, 0.255, 0.19), mat=mat_hair)
    lib.parent_part_to_bone(hair_top, arm_obj, "Head")

    for side in (-1, 1):
        front_wave = create_sphere(
            f"Zeus_HairFrontWave_{side}",
            (side * 0.10, -0.14, 1.72),
            (0.12, 0.11, 0.075),
            rot_deg=(0, side * 15, 0),
            mat=mat_hair,
        )
        lib.parent_part_to_bone(front_wave, arm_obj, "Head")

        side_mane = create_sphere(
            f"Zeus_HairSideMane_{side}",
            (side * 0.23, 0.03, 1.48),
            (0.095, 0.15, 0.23),
            mat=mat_hair,
        )
        lib.parent_part_to_bone(side_mane, arm_obj, "Head")

        low_curl = create_sphere(
            f"Zeus_HairSideCurl_{side}",
            (side * 0.24, 0.06, 1.32),
            (0.08, 0.11, 0.13),
            mat=mat_hair,
        )
        lib.parent_part_to_bone(low_curl, arm_obj, "Head")

    hair_back_main = create_box(
        "Zeus_HairBackMain",
        (0, 0.16, 1.44),
        (0.48, 0.19, 0.45),
        bevel_width=0.07,
        subsurf=1,
        mat=mat_hair,
    )
    lib.parent_part_to_bone(hair_back_main, arm_obj, "Head")

    for idx, x_off in enumerate((-0.18, -0.09, 0.0, 0.09, 0.18)):
        lock = create_sphere(
            f"Zeus_HairWave_{idx}",
            (x_off, 0.22, 1.29 - abs(x_off) * 0.22),
            (0.09, 0.08, 0.19),
            rot_deg=(14, 0, 0),
            mat=mat_hair,
        )
        lib.parent_part_to_bone(lock, arm_obj, "Head")

    # Golden Laurel Wreath Crown + 6 Leaves per side
    wreath_band = create_cylinder(
        "Gold_LaurelBand",
        (0, -0.01, 1.665),
        radius=0.258,
        depth=0.032,
        scale=(1.0, 0.98, 1.0),
        rot_deg=(-6, 0, 0),
        mat=mat_gold,
    )
    lib.parent_part_to_bone(wreath_band, arm_obj, "Head")

    for side in (-1, 1):
        for i in range(6):
            angle_rad = math.radians(16 + i * 24)
            lx = side * 0.262 * math.sin(angle_rad)
            ly = -0.256 * math.cos(angle_rad)
            lz = 1.675 + (2 - abs(i - 2)) * 0.008
            leaf = create_box(
                f"Gold_LaurelLeaf_{side}_{i}",
                (lx, ly, lz),
                (0.028, 0.095, 0.065),
                rot_deg=(28, side * 22, side * (25 + i * 22)),
                bevel_width=0.01,
                mat=mat_gold,
            )
            lib.parent_part_to_bone(leaf, arm_obj, "Head")

    # 4. Muscular Arms, Golden Wrist Bracers & Hands (Arm.L / Arm.R)
    for side, bname in ((1, "Arm.L"), (-1, "Arm.R")):
        shoulder = create_sphere(f"Shoulder_{bname}", (side * 0.34, 0, 1.18), (0.145, 0.135, 0.145), mat=mat_skin)
        lib.parent_part_to_bone(shoulder, arm_obj, bname)

        bicep = create_cylinder(
            f"UpperArm_{bname}",
            (side * 0.42, 0, 1.00),
            radius=0.108,
            depth=0.28,
            rot_deg=(0, side * -18, 0),
            mat=mat_skin,
        )
        lib.parent_part_to_bone(bicep, arm_obj, bname)

        forearm = create_cylinder(
            f"Forearm_{bname}",
            (side * 0.50, -0.03, 0.80),
            radius=0.095,
            depth=0.24,
            rot_deg=(10, side * -12, 0),
            mat=mat_skin,
        )
        lib.parent_part_to_bone(forearm, arm_obj, bname)

        bracer = create_cylinder(
            f"Gold_Bracer_{bname}",
            (side * 0.52, -0.04, 0.77),
            radius=0.108,
            depth=0.165,
            rot_deg=(10, side * -12, 0),
            mat=mat_gold,
        )
        lib.parent_part_to_bone(bracer, arm_obj, bname)

        hand = create_box(
            f"Hand_{bname}",
            (side * 0.54, -0.07, 0.65),
            (0.125, 0.135, 0.125),
            bevel_width=0.03,
            mat=mat_skin,
        )
        lib.parent_part_to_bone(hand, arm_obj, bname)

    # 5. Sturdy Legs & Greek Leather Sandals (Leg.L / Leg.R)
    for side, bname in ((1, "Leg.L"), (-1, "Leg.R")):
        leg_x = side * 0.16
        calf = create_cylinder(f"Leg_{bname}", (leg_x, 0, 0.25), radius=0.108, depth=0.38, mat=mat_skin)
        lib.parent_part_to_bone(calf, arm_obj, bname)

        foot = create_box(f"Foot_{bname}", (leg_x, -0.05, 0.06), (0.15, 0.26, 0.08), bevel_width=0.025, mat=mat_skin)
        lib.parent_part_to_bone(foot, arm_obj, bname)

        sole = create_box(f"SandalSole_{bname}", (leg_x, -0.05, 0.02), (0.17, 0.29, 0.035), bevel_width=0.01, mat=mat_leather)
        lib.parent_part_to_bone(sole, arm_obj, bname)

        for sy, sz in ((-0.11, 0.07), (-0.03, 0.08), (0.01, 0.13)):
            strap = create_box(
                f"SandalStrap_{bname}_{sy}",
                (leg_x, sy, sz),
                (0.175, 0.04, 0.04),
                bevel_width=0.008,
                mat=mat_leather,
            )
            lib.parent_part_to_bone(strap, arm_obj, bname)

    # 6. Glowing Cyan Lightning Bolt in Right Fist
    bolt = create_lightning_bolt("Zeus_LightningBolt", mat_lightning)
    lib.parent_part_to_bone(bolt, arm_obj, "Arm.R")

    # 7. Animations & Export
    lib.build_humanoid_animations(arm_obj)
    add_thunder_strike_animation(arm_obj)

    os.makedirs(os.path.dirname(os.path.abspath(output_glb)), exist_ok=True)
    if output_blend:
        os.makedirs(os.path.dirname(os.path.abspath(output_blend)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=output_blend)
    lib.export_glb(output_glb)
    return arm_obj


def render_6panel_turnaround(arm_obj: bpy.types.Object, output_png: str, panel_w: int = 440, panel_h: int = 440) -> None:
    """Render a 6-panel character sheet matching /workspaces/testmobie/zues.png:
    FRONT | BACK | LEFT SIDE
    RIGHT SIDE | THREE-QUARTER (Action Pose) | PORTRAIT
    """
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = panel_w
    scene.render.resolution_y = panel_h
    scene.render.film_transparent = False

    if not scene.world:
        scene.world = bpy.data.worlds.new("SheetWorld")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.82, 0.82, 0.82, 1.0)
        bg.inputs[1].default_value = 1.0

    center_full = Vector((0, 0, 0.92))
    center_portrait = Vector((0, -0.05, 1.50))

    # 3-point lighting around character
    for lname, loc, energy in [
        ("Key_Front", (1.8, -3.2, 2.6), 3.2),
        ("Fill_Left", (-2.5, -2.2, 1.8), 1.8),
        ("Back_Key", (0.0, 3.2, 2.5), 2.8),
        ("Side_Fill", (3.0, 0.5, 1.8), 1.8),
    ]:
        ldata = bpy.data.lights.new(name=lname, type="SUN")
        ldata.energy = energy
        lobj = bpy.data.objects.new(name=lname, object_data=ldata)
        scene.collection.objects.link(lobj)
        lobj.location = Vector(loc)
        lobj.rotation_euler = (center_full - lobj.location).to_track_quat("-Z", "Y").to_euler()

    cam_data = bpy.data.cameras.new("SheetCam")
    cam_data.lens = 55
    cam_obj = bpy.data.objects.new("SheetCam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    tmp_dir = tempfile.mkdtemp(prefix="zeus_sheet_")
    panels = [
        ("FRONT", center_full, Vector((0, -3.55, 0.12)), False),
        ("BACK", center_full, Vector((0, 3.55, 0.12)), False),
        ("LEFT SIDE", center_full, Vector((3.55, 0, 0.12)), False),
        ("RIGHT SIDE", center_full, Vector((-3.55, 0, 0.12)), False),
        ("THREE-QUARTER", center_full, Vector((-2.45, -2.55, 0.25)), True),
        ("PORTRAIT", center_portrait, Vector((0, -1.55, 0.04)), False),
    ]

    try:
        for idx, (label, target, offset, action_pose) in enumerate(panels):
            # Pose character for THREE-QUARTER action shot
            for pb in arm_obj.pose.bones:
                pb.location = (0, 0, 0)
                pb.rotation_euler = (0, 0, 0)
            if action_pose:
                arm_obj.pose.bones["Arm.R"].rotation_euler = (-1.25, 0.0, -0.25)
                arm_obj.pose.bones["Arm.L"].rotation_euler = (0.35, 0.0, 0.40)
                arm_obj.pose.bones["Leg.L"].rotation_euler = (-0.25, 0.0, 0.08)
                arm_obj.pose.bones["Leg.R"].rotation_euler = (0.25, 0.0, -0.08)
            bpy.context.view_layer.update()

            cam_obj.location = target + offset
            cam_obj.rotation_euler = (target - cam_obj.location).to_track_quat("-Z", "Y").to_euler()
            out_file = os.path.join(tmp_dir, f"panel_{idx}.png")
            scene.render.filepath = out_file
            bpy.ops.render.render(write_still=True)

        # Compose 3x2 sheet with borders and labels matching zues.png
        pad = 24
        label_h = 38
        sheet_w = pad * 4 + panel_w * 3
        sheet_h = pad * 3 + (panel_h + label_h) * 2
        sheet = Image.new("RGB", (sheet_w, sheet_h), (229, 229, 227))
        draw = ImageDraw.Draw(sheet)

        for idx, (label, _, _, _) in enumerate(panels):
            col = idx % 3
            row = idx // 3
            x = pad + col * (panel_w + pad)
            y = pad + row * (panel_h + label_h + pad)
            pfile = os.path.join(tmp_dir, f"panel_{idx}.png")
            if os.path.exists(pfile):
                img = Image.open(pfile).convert("RGB")
                sheet.paste(img, (x, y))
                draw.rectangle([x, y, x + panel_w, y + panel_h], outline=(160, 160, 160), width=2)
                draw.text((x + panel_w // 2 - len(label) * 4, y + panel_h + 10), label, fill=(25, 25, 25))

        os.makedirs(os.path.dirname(os.path.abspath(output_png)), exist_ok=True)
        sheet.save(output_png)
        print(f"[ZeusGen] Saved 6-panel turnaround sheet at: {output_png}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    out_glb = argv[0] if len(argv) > 0 else "/workspaces/testmobie/models/zeus.glb"
    out_blend = argv[1] if len(argv) > 1 else "/workspaces/testmobie/models/zeus.blend"
    out_sheet = argv[2] if len(argv) > 2 else "/workspaces/testmobie/models/zeus_turnaround_6views.png"
    rig = build_zeus(out_glb, out_blend)
    render_6panel_turnaround(rig, out_sheet)
