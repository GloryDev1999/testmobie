"""
Sample Parametric 3D Character / Bot / Monster Batch Generator for Blender 4.0+.
Usage:
  blender --background --factory-startup --python sample_batch_generator.py -- <output_dir> <count> <seed>
Generates `count` distinct stylized 3D models (.glb), each complete with:
  - Custom proportions, head style (Cube, Sphere, Horned, Visor), body armor, and PBR color palette
  - Full Humanoid Armature Rig (Root, Hips, Spine, Head, Arm.L/R, Leg.L/R)
  - 3 embedded NLA animations: Idle, Walk, Jump
"""

from __future__ import annotations
import os
import random
import sys
import bpy
import rig_and_anim_lib as lib


PALETTES = [
    # (Primary RGBA, Secondary RGBA, Accent/Visor Emission RGBA)
    ((0.18, 0.48, 0.92, 1.0), (0.88, 0.91, 0.95, 1.0), (0.10, 0.95, 1.00, 1.0)),  # Cyber Blue
    ((0.90, 0.22, 0.25, 1.0), (0.20, 0.22, 0.26, 1.0), (1.00, 0.75, 0.10, 1.0)),  # Crimson Mech
    ((0.20, 0.75, 0.42, 1.0), (0.26, 0.30, 0.28, 1.0), (0.50, 1.00, 0.30, 1.0)),  # Emerald Ranger
    ((0.62, 0.28, 0.88, 1.0), (0.16, 0.14, 0.22, 1.0), (1.00, 0.30, 0.85, 1.0)),  # Void Purple
    ((0.95, 0.62, 0.14, 1.0), (0.30, 0.26, 0.22, 1.0), (0.20, 0.90, 1.00, 1.0)),  # Solar Gold
]


def generate_one_character(variant_idx: int, rng: random.Random, output_glb: str) -> None:
    lib.clear_scene()

    primary, secondary, accent = rng.choice(PALETTES)
    mat_primary = lib.create_pbr_material(f"Primary_{variant_idx}", primary, metallic=0.35, roughness=0.35)
    mat_secondary = lib.create_pbr_material(f"Secondary_{variant_idx}", secondary, metallic=0.5, roughness=0.45)
    mat_accent = lib.create_pbr_material(
        f"Accent_{variant_idx}", accent, metallic=0.1, roughness=0.2, emission_color=accent, emission_strength=2.5
    )

    arm_obj = lib.create_humanoid_rig(name=f"HeroRig_{variant_idx}", scale=1.0)

    torso_w = rng.uniform(0.24, 0.34)
    head_scale = rng.uniform(0.22, 0.30)
    head_type = rng.choice(["rounded_cube", "sphere", "horned"])

    # 1. Torso (bound to Spine)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 1.02))
    torso = bpy.context.active_object
    torso.name = "Torso"
    torso.scale = (torso_w, 0.20, 0.26)
    bpy.ops.object.transform_apply(scale=True)
    bevel = torso.modifiers.new(name="Bevel", type="BEVEL")
    bevel.width = 0.04
    bevel.segments = 2
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    lib.assign_material(torso, mat_primary)
    lib.parent_part_to_bone(torso, arm_obj, "Spine")

    # 2. Hips / Pelvis (bound to Hips)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.68))
    hips = bpy.context.active_object
    hips.name = "Pelvis"
    hips.scale = (torso_w * 0.88, 0.18, 0.10)
    bpy.ops.object.transform_apply(scale=True)
    lib.assign_material(hips, mat_secondary)
    lib.parent_part_to_bone(hips, arm_obj, "Hips")

    # 3. Head + Visor (bound to Head)
    if head_type == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=12, radius=head_scale, location=(0, 0, 1.50))
    else:
        bpy.ops.mesh.primitive_cube_add(size=head_scale * 1.8, location=(0, 0, 1.50))
    head = bpy.context.active_object
    head.name = "HeadMesh"
    if head_type != "sphere":
        b = head.modifiers.new(name="Bevel", type="BEVEL")
        b.width = 0.05
        b.segments = 2
        bpy.ops.object.modifier_apply(modifier=b.name)
    lib.assign_material(head, mat_primary)
    lib.parent_part_to_bone(head, arm_obj, "Head")

    # Glowing Visor
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, -head_scale * 0.85, 1.52))
    visor = bpy.context.active_object
    visor.name = "Visor"
    visor.scale = (head_scale * 0.75, 0.04, head_scale * 0.28)
    bpy.ops.object.transform_apply(scale=True)
    lib.assign_material(visor, mat_accent)
    lib.parent_part_to_bone(visor, arm_obj, "Head")

    # Optional Horns / Antenna
    if head_type == "horned":
        for side in (-1, 1):
            bpy.ops.mesh.primitive_cone_add(
                vertices=8, radius1=0.05, radius2=0.01, depth=0.22, location=(side * head_scale * 0.65, 0, 1.76)
            )
            horn = bpy.context.active_object
            horn.name = f"Horn_{side}"
            lib.assign_material(horn, mat_accent)
            lib.parent_part_to_bone(horn, arm_obj, "Head")

    # 4. Arms (bound to Arm.L / Arm.R)
    for side, bname in ((1, "Arm.L"), (-1, "Arm.R")):
        bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.075, depth=0.42, location=(side * (torso_w + 0.10), 0, 1.00))
        arm = bpy.context.active_object
        arm.name = f"Mesh_{bname}"
        lib.assign_material(arm, mat_secondary)
        lib.parent_part_to_bone(arm, arm_obj, bname)

    # 5. Legs (bound to Leg.L / Leg.R)
    for side, bname in ((1, "Leg.L"), (-1, "Leg.R")):
        bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.09, depth=0.52, location=(side * 0.15, 0, 0.30))
        leg = bpy.context.active_object
        leg.name = f"Mesh_{bname}"
        lib.assign_material(leg, mat_secondary)
        lib.parent_part_to_bone(leg, arm_obj, bname)

    # 6. Build Idle, Walk, Jump animations
    lib.build_humanoid_animations(arm_obj)

    # 7. Export GLB
    os.makedirs(os.path.dirname(os.path.abspath(output_glb)), exist_ok=True)
    lib.export_glb(output_glb)


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    output_dir = argv[0] if len(argv) > 0 else "/tmp/models_out"
    count = int(argv[1]) if len(argv) > 1 else 1
    seed = int(argv[2]) if len(argv) > 2 else 42

    rng = random.Random(seed)
    os.makedirs(output_dir, exist_ok=True)
    for i in range(1, count + 1):
        out_file = os.path.join(output_dir, f"character_{i:03d}.glb")
        generate_one_character(i, rng, out_file)
        print(f"[BatchGen] Generated ({i}/{count}): {out_file}")


if __name__ == "__main__":
    main()
