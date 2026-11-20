"""첫 화면 배경: 햇빛 드는 주방에 LG 빌트인 제품(카탈로그 치수 glb)을 붙박이로 넣고 Cycles로 렌더한다.

실행: python render_hero.py -- 출력.png 가로 세로 샘플수   (예: -- hero.png 2400 1350 80, bpy 필요)
결과는 apps/web/img/hero-kitchen.webp(그대로), hero-kitchen-m.webp(가로 1150~2050 잘라 720×1080)로 저장한다.
"""
import bpy, math, sys
from pathlib import Path
from mathutils import Vector
M = str(Path(__file__).resolve().parents[4] / "apps" / "web" / "models" / "products") + "/"
OUT = sys.argv[sys.argv.index("--")+1]
W, H, SAMPLES = int(sys.argv[-3]), int(sys.argv[-2]), int(sys.argv[-1])
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

def mat(name, rgb, rough=0.6, metal=0.0, spec=0.5, coat=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if coat: b.inputs["Coat Weight"].default_value = coat
    return m

def srgb(h):
    h = h.lstrip("#"); c = [int(h[i:i+2], 16)/255 for i in (0, 2, 4)]
    return tuple(x/12.92 if x <= 0.04045 else ((x+0.055)/1.055)**2.4 for x in c)

def box(name, x0, x1, y0, y1, z0, z1, m):
    bpy.ops.mesh.primitive_cube_add(size=1, location=((x0+x1)/2, (y0+y1)/2, (z0+z1)/2))
    o = bpy.context.object; o.name = name
    o.scale = (x1-x0, y1-y0, z1-z0); bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(m)
    bev = o.modifiers.new("b", "BEVEL"); bev.width = 0.003; bev.segments = 2
    return o

plaster = mat("plaster", srgb("#E6DFD3"), 0.9)
cab = mat("cabinet", srgb("#EFEBE4"), 0.42)
cabdark = mat("cabdark", srgb("#CFC8BC"), 0.5)
stone = mat("stone", srgb("#F4F2EE"), 0.18, coat=0.3)
shadowgap = mat("gap", srgb("#2a2826"), 0.7)
frame = mat("frame", srgb("#3B3A38"), 0.35, metal=0.6)
glass = bpy.data.materials.new("glass"); glass.use_nodes = True
gb = glass.node_tree.nodes["Principled BSDF"]
gb.inputs["Transmission Weight"].default_value = 1.0; gb.inputs["Roughness"].default_value = 0.0

# 바닥: 원목 느낌 (노이즈로 결)
floor = bpy.data.materials.new("oak"); floor.use_nodes = True
nt = floor.node_tree; bs = nt.nodes["Principled BSDF"]
tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
mp.inputs["Scale"].default_value = (0.5, 22, 1)
wave = nt.nodes.new("ShaderNodeTexNoise"); wave.inputs["Scale"].default_value = 6; wave.inputs["Detail"].default_value = 8
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].color = (*srgb("#A88E72"), 1); ramp.color_ramp.elements[1].color = (*srgb("#CDB89C"), 1)
nt.links.new(tc.outputs["Object"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], wave.inputs["Vector"])
nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"]); nt.links.new(ramp.outputs["Color"], bs.inputs["Base Color"])
bs.inputs["Roughness"].default_value = 0.38; bs.inputs["Coat Weight"].default_value = 0.15

# 방: 바닥, 뒷벽(y=2.2), 왼벽(x=-2.6, 큰 창), 오른벽(x=4.4), 천장
box("floor", -3, 5, -6, 2.2, -0.05, 0, floor)
box("ceil", -3, 5, -6, 2.4, 2.7, 2.8, plaster)
box("back", -3, 5, 2.2, 2.4, 0, 2.7, plaster)
box("right", 4.4, 4.6, -6, 2.2, 0, 2.7, plaster)
# 왼벽: 창 구멍 y -3.2~1.6, z 0.35~2.45
wx0, wx1 = -2.8, -2.6
box("lw1", wx0, wx1, -6, -3.2, 0, 2.7, plaster)
box("lw2", wx0, wx1, 1.6, 2.2, 0, 2.7, plaster)
box("lw3", wx0, wx1, -3.2, 1.6, 0, 0.35, plaster)
box("lw4", wx0, wx1, -3.2, 1.6, 2.45, 2.7, plaster)
for i, y in enumerate([-3.2, -1.6, 0.0, 1.6]):
    box(f"mul{i}", wx0+0.06, wx1-0.06, y-0.03, y+0.03, 0.35, 2.45, frame)
box("mulh", wx0+0.06, wx1-0.06, -3.2, 1.6, 1.98, 2.02, frame)
g = box("glass", wx0+0.09, wx0+0.1, -3.2, 1.6, 0.35, 2.45, glass)
g.visible_shadow = False

# 빌트인 벽장 (뒷벽 앞, 깊이 0.72): x 0.0 ~ 4.4
D0 = 2.2 - 0.72
box("tallL", -0.1, 0.0, D0, 2.2, 0, 1.88, cab)  # 측판
def place(sku, x_left, z0=0.0, y_front=D0+0.02):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=M + sku + ".glb")
    objs = [o for o in bpy.data.objects if o not in before]
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    off = Vector((x_left - mn.x, y_front - mn.y, z0 - mn.z))
    for o in objs:
        if o.parent is None: o.location += off
    return mx.x - mn.x, mx.z - mn.z
x = 0.0
# 냉장고 + 김치냉장고 붙박이, 위는 수납장
w, h = place("G646GBB031", x + 0.01); x += w + 0.02
w2, h2 = place("Z386GBB281", x + 0.01); x += w2 + 0.02
box("upper", -0.1, x, D0, 2.2, 1.88, 2.5, cab)
box("upgap", -0.1, x, D0-0.002, D0, 1.865, 1.875, shadowgap)
box("tallR", x, x + 0.04, D0, 2.2, 0, 1.88, cab)
x += 0.04
# 하부장 + 식기세척기 + 상판, 위 오픈 선반 대신 민벽
xs = x
place("DUE6BGE", x + 0.02, z0=0.1, y_front=D0 + 0.03); x += 0.62
box("base1", x, 4.4, D0 + 0.12, 2.2, 0.1, 0.86, cab)
for i, xx in enumerate([x + 0.6, x + 1.2]):
    box(f"bg{i}", xx - 0.002, xx + 0.002, D0 + 0.115, D0 + 0.12, 0.1, 0.86, shadowgap)
box("kick", xs, 4.4, D0 + 0.2, 2.2, 0, 0.1, cabdark)
box("top", xs, 4.4, D0 + 0.08, 2.2, 0.86, 0.9, stone)
place("WU523AWB", x + 0.9, z0=0.9, y_front=D0 + 0.35)
# 아일랜드 + 인덕션
ix0, ix1, iy0, iy1 = 1.0, 3.4, -0.6, 0.35
box("island", ix0 + 0.03, ix1 - 0.03, iy0 + 0.05, iy1 - 0.03, 0.08, 0.88, cab)
box("ikick", ix0 + 0.1, ix1 - 0.1, iy0 + 0.12, iy1 - 0.1, 0, 0.08, cabdark)
box("itop", ix0, ix1, iy0, iy1, 0.88, 0.92, stone)
place("BEI3QKBLOE", 1.9, z0=0.905, y_front=-0.42)

pend = mat("pend", srgb("#2B2A28"), 0.3, metal=0.8)
glow = bpy.data.materials.new("glow"); glow.use_nodes=True
gn = glow.node_tree.nodes["Principled BSDF"]; gn.inputs["Emission Color"].default_value=(1,0.82,0.6,1); gn.inputs["Emission Strength"].default_value=6
for px in (1.65, 2.75):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.004, depth=1.0, location=(px,-0.12,2.2)); bpy.context.object.data.materials.append(pend)
    bpy.ops.mesh.primitive_cone_add(radius1=0.17, radius2=0.03, depth=0.22, location=(px,-0.12,1.6)); bpy.context.object.data.materials.append(pend)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.045, location=(px,-0.12,1.5)); bpy.context.object.data.materials.append(glow)
# 빛: 해(왼쪽 창으로 비스듬히), 하늘
sun = bpy.data.lights.new("sun", "SUN"); sun.energy = 7.5; sun.angle = math.radians(1.2)
sun.color = (1.0, 0.9, 0.78)
so = bpy.data.objects.new("sun", sun); sc.collection.objects.link(so)
so.rotation_euler = (math.radians(66), 0, math.radians(-58))
world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
bg = world.node_tree.nodes["Background"]; bg.inputs["Color"].default_value = (0.62, 0.72, 0.9, 1); bg.inputs["Strength"].default_value = 0.35
# 창 바깥 하늘 빛을 방 안으로 (area light)
al = bpy.data.lights.new("win", "AREA"); al.energy = 140; al.shape = "RECTANGLE"; al.size = 4.8; al.size_y = 2.1
al.color = (0.86, 0.91, 1.0)
ao = bpy.data.objects.new("win", al); sc.collection.objects.link(ao)
ao.location = (-2.9, -0.8, 1.4); ao.rotation_euler = (0, math.radians(-90), 0)
fill = bpy.data.lights.new("fill", "AREA"); fill.energy = 45; fill.size = 3
fo = bpy.data.objects.new("fill", fill); sc.collection.objects.link(fo)
fo.location = (1.4, -3.5, 2.6); fo.rotation_euler = (math.radians(60), 0, 0)

cam = bpy.data.cameras.new("cam"); cam.lens = 26
co = bpy.data.objects.new("cam", cam); sc.collection.objects.link(co); sc.camera = co
co.location = (-1.7, -3.9, 1.2)
d = Vector((-0.75, 2.0, 1.1)) - co.location
co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

sc.render.engine = "CYCLES"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.cycles.device = "CPU"; sc.render.resolution_x = W; sc.render.resolution_y = H
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
sc.cycles.max_bounces = 6
sc.view_settings.exposure = -0.3
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("OK", OUT)
