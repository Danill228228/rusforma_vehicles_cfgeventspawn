"""Smoke-тест 3D-конвейера: Blender headless создаёт тестовый ящик с LOD, UV и материалом,
сохраняет .blend и экспортирует FBX/OBJ/glTF. Печатает JSON с результатами.

Запуск:  PY=$(bash AI_Company_DayZMods/Company/Tools/setup_blender.sh)
         $PY AI_Company_DayZMods/Company/Tools/blender_smoke_test.py /tmp/dzm_blender_test
"""
import json
import os
import sys

import bpy

out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "/tmp/dzm_blender_test")
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)

material = bpy.data.materials.new("dzm_crate_mat")
results = {"blender": bpy.app.version_string, "lods": {}, "files": {}}

# Три LOD одного объекта: подразделение уменьшается с номером LOD (принцип, который проверяет QA)
for lod, cuts in ((0, 6), (1, 2), (2, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(lod * 1.5, 0, 0.5))
    obj = bpy.context.active_object
    obj.name = f"crate_lod{lod}"
    if cuts:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.subdivide(number_cuts=cuts)
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15)
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.data.materials.append(material)
    mesh = obj.data
    mesh.calc_loop_triangles()
    results["lods"][obj.name] = {
        "verts": len(mesh.vertices),
        "tris": len(mesh.loop_triangles),
        "uv_layers": len(mesh.uv_layers),
    }

blend = os.path.join(out, "crate_test.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend)
exports = {
    "fbx": lambda p: bpy.ops.export_scene.fbx(filepath=p),
    "obj": lambda p: bpy.ops.wm.obj_export(filepath=p),
    "glb": lambda p: bpy.ops.export_scene.gltf(filepath=p),
}
for ext, func in exports.items():
    path = os.path.join(out, f"crate_test.{ext}")
    try:
        func(path)
        results["files"][ext] = {"ok": os.path.exists(path), "bytes": os.path.getsize(path)}
    except Exception as exc:  # фиксируем, а не роняем тест: QA должен видеть, что именно не работает
        results["files"][ext] = {"ok": False, "error": str(exc)[:200]}
results["files"]["blend"] = {"ok": os.path.exists(blend), "bytes": os.path.getsize(blend)}
tris = [v["tris"] for v in results["lods"].values()]
results["lod_order_ok"] = tris == sorted(tris, reverse=True)
results["ok"] = results["lod_order_ok"] and all(f.get("ok") for f in results["files"].values())
print(json.dumps(results, ensure_ascii=False, indent=2))
sys.exit(0 if results["ok"] else 1)
