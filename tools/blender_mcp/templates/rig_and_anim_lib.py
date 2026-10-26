"""
Reusable Procedural Rigging, Keyframe Animation & PBR Material Library for Blender 4.0+ (bpy).
Designed for zero-cost batch generation of 100+ 3D models & animations in headless CLI.
"""

from __future__ import annotations
import math
import bpy
from mathutils import Vector, Euler


def clear_scene() -> None:
    """Reset the Blender scene completely (objects, meshes, armatures, actions, materials)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for collection in (
        bpy.data.objects,
        bpy.data.meshes,
        bpy.data.armatures,
        bpy.data.materials,
        bpy.data.actions,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for item in list(collection):
            collection.remove(item)


def create_pbr_material(
    name: str,
    base_color: tuple[float, float, float, float] = (0.8, 0.8, 0.8, 1.0),
    metallic: float = 0.0,
    roughness: float = 0.4,
    emission_color: tuple[float, float, float, float] | None = None,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    """Create a glTF-compatible Principled BSDF material."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = base_color
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
        if emission_color and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = emission_color
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


def assign_material(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    """Assign a material to a mesh object."""
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def create_humanoid_rig(name: str = "CharacterRig", scale: float = 1.0) -> bpy.types.Object:
    """Create a standard game-ready humanoid armature (Root, Spine, Head, Arms, Legs)."""
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    arm_obj = bpy.context.active_object
    arm_obj.name = name
    arm = arm_obj.data
    arm.name = f"{name}_Data"

    # Remove default bone
    for b in list(arm.edit_bones):
        arm.edit_bones.remove(b)

    def add_bone(bname: str, head: tuple[float, float, float], tail: tuple[float, float, float], parent=None):
        b = arm.edit_bones.new(bname)
        b.head = Vector(head) * scale
        b.tail = Vector(tail) * scale
        if parent:
            b.parent = parent
        return b

    root = add_bone("Root", (0, 0, 0.0), (0, 0, 0.25))
    hips = add_bone("Hips", (0, 0, 0.55), (0, 0, 0.85), root)
    spine = add_bone("Spine", (0, 0, 0.85), (0, 0, 1.25), hips)
    head = add_bone("Head", (0, 0, 1.25), (0, 0, 1.75), spine)

    arm_l = add_bone("Arm.L", (0.28, 0, 1.20), (0.62, 0, 0.80), spine)
    arm_r = add_bone("Arm.R", (-0.28, 0, 1.20), (-0.62, 0, 0.80), spine)

    leg_l = add_bone("Leg.L", (0.16, 0, 0.55), (0.16, 0, 0.05), hips)
    leg_r = add_bone("Leg.R", (-0.16, 0, 0.55), (-0.16, 0, 0.05), hips)

    bpy.ops.object.mode_set(mode="OBJECT")
    return arm_obj


def parent_part_to_bone(mesh_obj: bpy.types.Object, arm_obj: bpy.types.Object, bone_name: str) -> None:
    """Bind a rigid mesh part to a specific bone via vertex group + Armature modifier (100% glTF compatible)."""
    vg = mesh_obj.vertex_groups.get(bone_name) or mesh_obj.vertex_groups.new(name=bone_name)
    vert_indices = [v.index for v in mesh_obj.data.vertices]
    vg.add(vert_indices, 1.0, "REPLACE")

    mesh_obj.parent = arm_obj
    mod = mesh_obj.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = arm_obj


def build_humanoid_animations(arm_obj: bpy.types.Object, fps: int = 24) -> list[str]:
    """Attach 3 reusable NLA animation tracks (Idle, Walk, Jump) to a humanoid armature."""
    bpy.context.scene.render.fps = fps
    if not arm_obj.animation_data:
        arm_obj.animation_data_create()

    for pb in arm_obj.pose.bones:
        pb.rotation_mode = "XYZ"

    created_actions = []

    def reset_pose():
        for pb in arm_obj.pose.bones:
            pb.location = (0, 0, 0)
            pb.rotation_euler = (0, 0, 0)
            pb.scale = (1, 1, 1)

    def push_nla(action: bpy.types.Action):
        action.use_fake_user = True
        track = arm_obj.animation_data.nla_tracks.new()
        track.name = action.name
        strip = track.strips.new(action.name, int(action.frame_range[0]), action)
        strip.name = action.name
        created_actions.append(action.name)

    # 1. Idle Animation (Frames 1..32)
    act_idle = bpy.data.actions.new(name="Idle")
    arm_obj.animation_data.action = act_idle
    for f, z_off, pitch in [(1, 0.0, 0.0), (16, 0.04, 0.06), (32, 0.0, 0.0)]:
        reset_pose()
        arm_obj.pose.bones["Hips"].location = (0, 0, z_off)
        arm_obj.pose.bones["Spine"].rotation_euler = (pitch, 0, 0)
        arm_obj.pose.bones["Arm.L"].rotation_euler = (0, 0, 0.08 if f == 16 else 0.0)
        arm_obj.pose.bones["Arm.R"].rotation_euler = (0, 0, -0.08 if f == 16 else 0.0)
        for bname in ("Hips", "Spine", "Head", "Arm.L", "Arm.R", "Leg.L", "Leg.R"):
            pb = arm_obj.pose.bones[bname]
            pb.keyframe_insert(data_path="location", frame=f)
            pb.keyframe_insert(data_path="rotation_euler", frame=f)
    push_nla(act_idle)

    # 2. Walk Animation (Frames 1..24)
    act_walk = bpy.data.actions.new(name="Walk")
    arm_obj.animation_data.action = act_walk
    Swing = 0.55
    for f, sgn, bob in [(1, 1.0, 0.0), (7, 0.0, 0.05), (13, -1.0, 0.0), (19, 0.0, 0.05), (24, 1.0, 0.0)]:
        reset_pose()
        arm_obj.pose.bones["Hips"].location = (0, 0, bob)
        arm_obj.pose.bones["Leg.L"].rotation_euler = (Swing * sgn, 0, 0)
        arm_obj.pose.bones["Leg.R"].rotation_euler = (-Swing * sgn, 0, 0)
        arm_obj.pose.bones["Arm.L"].rotation_euler = (-Swing * 0.7 * sgn, 0, 0)
        arm_obj.pose.bones["Arm.R"].rotation_euler = (Swing * 0.7 * sgn, 0, 0)
        for bname in ("Hips", "Spine", "Head", "Arm.L", "Arm.R", "Leg.L", "Leg.R"):
            pb = arm_obj.pose.bones[bname]
            pb.keyframe_insert(data_path="location", frame=f)
            pb.keyframe_insert(data_path="rotation_euler", frame=f)
    push_nla(act_walk)

    # 3. Jump / Celebrate Animation (Frames 1..24)
    act_jump = bpy.data.actions.new(name="Jump")
    arm_obj.animation_data.action = act_jump
    for f, z_off, arm_rot in [(1, 0.0, 0.0), (6, -0.08, -0.3), (13, 0.35, 1.2), (20, -0.05, 0.2), (24, 0.0, 0.0)]:
        reset_pose()
        arm_obj.pose.bones["Hips"].location = (0, 0, z_off)
        arm_obj.pose.bones["Arm.L"].rotation_euler = (-arm_rot, 0, 0)
        arm_obj.pose.bones["Arm.R"].rotation_euler = (-arm_rot, 0, 0)
        for bname in ("Hips", "Spine", "Head", "Arm.L", "Arm.R", "Leg.L", "Leg.R"):
            pb = arm_obj.pose.bones[bname]
            pb.keyframe_insert(data_path="location", frame=f)
            pb.keyframe_insert(data_path="rotation_euler", frame=f)
    push_nla(act_jump)

    arm_obj.animation_data.action = None
    return created_actions


def export_glb(output_path: str) -> None:
    """Export current scene to a compact .glb with animations and materials."""
    bpy.ops.export_scene.gltf(
        filepath=output_path,
        export_format="GLB",
        export_animations=True,
        export_nla_strips=True,
        export_yup=True,
        export_apply=False,
    )
