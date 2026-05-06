import array
import bmesh
import bpy
import io
import mathutils
import os
import numpy as np
import re
import struct
import time
from bpy_extras import anim_utils
from bpy_extras import image_utils
from bpy_extras.node_shader_utils import PrincipledBSDFWrapper
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace


global mtl_cache
global image_cache


def set_glob(params):
    global tm
    global bLightmaps
    global bBlendmaps
    global dirname
    global mtl_cache
    global image_cache
    tm,bLightmaps,bBlendmaps,dirname=params
    mtl_cache = {}
    image_cache = {}


@dataclass
class MeshIn:
    meshname: str
    numchannels: int
    numVerts: int
    verts: []
    numFaces: int
    faces: []
    nummat: int
    mat: []
    normalmap: str

    type: int
    index: int
    size: int
    offset: int


@dataclass
class Vertex:
    x: float
    y: float
    z: float
    nx: float
    ny: float
    nz: float
    u: float
    v: float
    u2: float
    v2: float


@dataclass
class Face:
    v0: int
    v1: int
    v2: int


@dataclass
class UV:
    u: float
    v: float


@dataclass
class Material:
    offset: int
    size: int
    colorMapName: str
    colorOffset: UV
    colorTiling: UV
    lightMapName: str
    lightOffset: UV
    lightTiling: UV
    blendMapName: str
    blendOffset: UV
    blendTiling: UV
    alphaMapName: str
    alphaOffset: UV
    alphaTiling: UV


@dataclass
class MeshOut:
    name: str
    bbox: []
    numUVs: int
    verts: []
    faces: []
    mtls: {}
    materials: []
    lm: ''
    type: int

    
zone = [
    'antyp',
    'barrier',
    'monster',
    'portal',
    'volfog',
    'vollight',
    'zone',
]

pkspc = mathutils.Matrix(( (1,0,0,0),(0,0,-1,0),(0,1,0,0),(0,0,0,1) ))


def writeString(file,name):
    value = name.encode('iso-8859-1', 'replace')
    binary_format = '<%ds' % (len(value) + 1)
    file.write(struct.pack(binary_format, value))


def write_short(file,value):
    file.write(struct.pack('<H',value))


def write_long(file,value):
    file.write(struct.pack('<I',value))


def write_float(file,value):
    file.write(struct.pack('<f',value))


def fname(filepath):
    return os.path.basename(filepath).split('.', 1)[0]


def getMaterial(mtl):
    material = {
    'color': 'notex',
    'c_loc': [0.0,0.0],
    'c_scl': [1.0,1.0],
    'light': None,
    'blend': '',
    'b_loc': [0.0,0.0],
    'b_scl': [1.0,1.0],
    'alpha': '',
    'PBimg': '', # likely 'Pre-Biased'
    }
    if mtl and mtl.use_nodes:
        wrapper = PrincipledBSDFWrapper(mtl)
        # normalmap
        try:
            normal = wrapper.node_principled_bsdf.inputs['Normal'].links[0].from_node
            tex_image = normal.inputs['Color'].links[0].from_node
            material['PBimg'] = fname(tex_image.image.name)
        except: pass
        # lightmap
        try:
            mix_rgb = wrapper.node_principled_bsdf.inputs['Emission Color'].links[0].from_node
            color = mix_rgb.inputs['Color2'].links[0].from_node
            tex_image = color.inputs['Color1'].links[0].from_node
            material['light'] = fname(tex_image.image.name)
        except: pass
        # diffuse only
        try:
            # color
            tex_image = wrapper.base_color_texture
            material['color'] = fname(tex_image.image.name)
            return material
        except: pass
        # blended
        try:
            mix_rgb = wrapper.node_principled_bsdf.inputs['Base Color'].links[0].from_node
            # color
            tex_image = mix_rgb.inputs['Color1'].links[0].from_node
            material['color'] = fname(tex_image.image.name)
            mapping = tex_image.inputs['Vector'].links[0].from_node        
            material['c_loc'] = mapping.inputs['Location'].default_value[0], mapping.inputs['Location'].default_value[1]
            material['c_scl'] = 1/mapping.inputs['Scale'].default_value[0], 1/mapping.inputs['Scale'].default_value[1]
            # blend
            tex_image = mix_rgb.inputs['Color2'].links[0].from_node
            material['blend'] = fname(tex_image.image.name)
            mapping = tex_image.inputs['Vector'].links[0].from_node
            material['b_loc'] = mapping.inputs['Location'].default_value[0], mapping.inputs['Location'].default_value[1]
            material['b_scl'] = 1/mapping.inputs['Scale'].default_value[0], 1/mapping.inputs['Scale'].default_value[1]
            # alpha
            tex_image = mix_rgb.inputs['Fac'].links[0].from_node
            material['alpha'] = fname(tex_image.image.name)
            return material
        except: pass
    return material


def triangulate_object( mesh, bSort ):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    if bSort:
        bm.faces.sort(key=lambda f: f.material_index)
        bm.faces.index_update()
    bm.to_mesh(mesh)
    bm.free()


def _map_n_pack( verts ):
    output = []
    for vert in verts:
        key = list(vert.keys())[0]
        normal = vert.get(key)
        output.append(key[0:12] + struct.pack('<3f', normal[0], normal[2], -normal[1]) + key[12:28])
    return output


def ConvertToMPKFaces( mesh, bRound, bOptimize ):
    match mesh.normals_domain:
        case 'POINT':
            normal_source = mesh.vertex_normals
        case 'CORNER' | 'FACE':
            normal_source = mesh.corner_normals
        case _:
            # Unreachable
            raise AssertionError('Unexpected normals domain \'%s\'' % mesh.normals_domain)

    np.empty(len(normal_source) * 3, dtype=[])
    t_normal = np.empty(len(normal_source) * 3, dtype=np.single)
    normal_source.foreach_get('vector', t_normal)

    uvl_1 = mesh.uv_layers[0].data[:] if len(mesh.uv_layers) > 0 else None
    uvl_2 = mesh.uv_layers[1].data[:] if len(mesh.uv_layers) > 1 else None
    srcvt = [] # for weights mapping
    verts = []
    faces = []
    vWritten = {}

    i = 0
    split = len(t_normal)/3 == len(mesh.polygons)*3

    for pl in mesh.polygons:
        ii = 0
        face = []
        for j,v in enumerate(pl.vertices):
            vert = {}
            # coords
            x,y,z = mesh.vertices[v].co
            if bRound: x = round(x,4); y = round(y,4); z = round(z,4)
            # UVs
            uv1 = uv2 = [0.0,1.0]
            if uvl_2 is not None:
                uv2=uvl_2[pl.loop_start + ii].uv
                uv1=uvl_1[pl.loop_start + ii].uv
            elif uvl_1 is not None:
                uv1=uvl_1[pl.loop_start + ii].uv
            ii += 1
            # normals
            idx = (v*3,i) [split]; i += 3
            vn = []
            for iii in range(3):
                vn.append(t_normal[idx + iii])
            normal = mathutils.Vector(vn)
            if bOptimize:
                key = struct.pack('<7f', x, z, -y, uv1[0], 1-uv1[1], uv2[0], 1-uv2[1])
                double = vWritten.get(key)
                if bool(double):
                    index = None
                    for vrt in double:
                        vdata = vrt.get(key)
                        if vdata and (vdata[0]@normal)>0.9999:
                            index = vdata[1]
                            break
                    if index is None:
                        vWritten[key].append({key : [normal,len(verts)]})
                        face.append(len(verts))
                        vert[key] = normal
                        verts.append(vert)
                    else: face.append(index)
                else:
                    vWritten[key] = [{key : [normal,len(verts)]}]
                    face.append(len(verts))
                    vert[key] = normal
                    verts.append(vert)
            else: # default
                key = struct.pack('<10f', x, z, -y, normal[0], normal[2], -normal[1], uv1[0], 1-uv1[1], uv2[0], 1-uv2[1])
                double = vWritten.get(v)
                if bool(double):
                    index = None
                    for vrt in double:
                        index = vrt.get(key)
                        if index: break
                    if index is None:
                        vWritten[v].append({key : len(verts)})
                        face.append(len(verts))
                        verts.append(key)
                    else: face.append(index)
                else:
                    vWritten[v] = [{key : len(verts)}]
                    face.append(len(verts))
                    verts.append(key)
            if len(verts)>len(srcvt): srcvt.append(v)
        faces.append(face)
    if bOptimize:
        return _map_n_pack(verts), faces, srcvt
    else:
        return verts, faces, srcvt


def getGeometry(file, context, global_matrix, params):

    (filetype, bOptimize, bAll, bSelection, bVisible, bSort, scale, *rest) = params
    try: arm_obj = rest[0]
    except: arm_obj = None

    scene = context.scene
    layer = context.view_layer
    depsgraph = context.evaluated_depsgraph_get()

    unit_measure = 1.0
    unit_length = scene.unit_settings.length_unit
    if unit_length == 'MILES':
        unit_measure = 0.000621371
    elif unit_length == 'KILOMETERS':
        unit_measure = 0.001
    elif unit_length == 'FEET':
        unit_measure = 3.280839895
    elif unit_length == 'INCHES':
        unit_measure = 39.37007874
    elif unit_length == 'CENTIMETERS':
        unit_measure = 100
    elif unit_length == 'MILLIMETERS':
        unit_measure = 1000
    elif unit_length == 'THOU':
        unit_measure = 39370.07874
    elif unit_length == 'MICROMETERS':
        unit_measure = 1000000

    mtx_scale = mathutils.Matrix.Scale((scale * unit_measure),4)

    if global_matrix is None:
        global_matrix = mathutils.Matrix()

    mesh_objects = []

    object_filter={'WORLD', 'MESH'}

    if bSelection:
        objects = [ob for ob in scene.objects if ob.type in object_filter and ob.visible_get(view_layer=layer) and ob.select_get(view_layer=layer)]
    elif bVisible:
        objects = [ob for ob in scene.objects if ob.type in object_filter and ob.visible_get(view_layer=layer)]
    elif bAll:
        objects = [ob for ob in scene.objects if ob.type in object_filter]

    active_object = context.view_layer.objects.active
    org_mode = None
    if active_object and active_object.mode != 'OBJECT' and bpy.ops.object.mode_set.poll():
        org_mode = active_object.mode
        bpy.ops.object.mode_set(mode='OBJECT')

    for ob in objects:
        if ob.type not in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}:
            continue
        arm_mod = next((mod for mod in ob.modifiers if mod.type == 'ARMATURE' and mod.object == arm_obj), None)
        if arm_obj and not arm_mod: continue

        ob_eval = ob.evaluated_get(depsgraph)
        try:
            data = ob_eval.to_mesh()
        except Exception:
            data = None

        if data:
            matrix = global_matrix @ ob.matrix_world
            data.transform(matrix)
            data.transform(mtx_scale)
            mesh_objects.append((ob, data, matrix))

    output = SimpleNamespace(geom = [], bIsItem = True)
    bSpecLimit = filetype=='DAT' or filetype=='PKMDL'
    limit = (0xffff,0xffffffff)[bSpecLimit]
    for ob, mesh, matrix in mesh_objects:
        triangulate_object( mesh, bSort )

        bRound = re.search(r'(?=(' + '|'.join(zone) + r'))', ob.name, re.IGNORECASE)
        verts, faces, srcvt = ConvertToMPKFaces( mesh, bRound, bOptimize )

        if len(verts) == 0 or len(faces) == 0: continue
        
        if len(verts)>limit:
            info('\'%s\' is rejected : too many vertices (> %d)' % (ob.name,limit), icon='WARNING')
            continue
        if len(faces)>limit:
            info('\'%s\' is rejected : too many faces (> %d)' % (ob.name,limit), icon='WARNING')
            continue
        if bSpecLimit:
            try:
                for f in faces:
                    assert(f[0]<=0xffff and f[2]<=0xffff and f[1]<=0xffff)
            except:
                info('\'%s\' is rejected : too many faces' % ob.name, icon='WARNING')
                continue

        mtls = {}; _idx = None; i=0
        for pl in mesh.polygons:
            idx = pl.material_index
            if _idx != idx:
                mtls[i]=[1,idx]
                _idx = idx
                i += 1
            else:
                mtl = mtls.get(i-1)
                mtls[i-1] = mtl[0]+1,mtl[1]

        try:
            mtl_offset = 0
            for mtl in mtls.values():
                assert(mtl_offset<=limit)
                mtl_offset += mtl[0]*3
        except:
            info('\'%s\' is rejected : too many faces' % ob.name, icon='WARNING')
            continue

        materials = ([getMaterial(None)],[])[bool(ob.material_slots)]
        for slot in ob.material_slots:
            mtl = getMaterial(slot.material)
            materials.append(mtl)

        numUVs = 2 if len(mesh.uv_layers) > 1 else 1

        LightMapName = ''
        if numUVs == 2:
            colls = ob.users_collection
            if colls[0].name != 'Scene Collection':
                LightMapName = colls[0].name
            else:
                LightMapName = ob.name + '_L_0000'

        # bounding box
        mtx_scale = mathutils.Matrix.Scale(scale, 4)
        bbox_corners = [ob.matrix_world @ mathutils.Vector(corner) for corner in ob.bound_box]
        p1 = bbox_corners[3] @ pkspc @ mtx_scale
        p2 = bbox_corners[5] @ pkspc @ mtx_scale
        bbox = struct.pack('<6f', p1.x, p1.y, p1.z, p2.x, p2.y, p2.z)

        match filetype:
            case 'DAT':
                type = 0x02                                                  # b00010
                if re.search(r'zone'  , ob.name, re.IGNORECASE): type = 0x04 # b00100
                if re.search(r'portal', ob.name, re.IGNORECASE): type = 0x08 # b01000
                if re.search(r'antyp' , ob.name, re.IGNORECASE): type = 0x10 # b10000
                if type != 0x02: output.bIsItem = False
                if type == 0x08:
                    verts = []
                    v0 = 3
                    v1 = (2,6)[p1.y==p2.y]
                    v2 = 5
                    v3 = (4,0)[p1.y==p2.y]
                    for v in [v0,v1,v2,v3]:
                        p = bbox_corners[v] @ pkspc
                        verts.append(struct.pack('<10f', p.x, p.y, p.z, 0,0,0,0,0,0,0))
                    faces = [[2,1,0],[0,3,2]]
                output.geom.append(MeshOut(ob.name, bbox, numUVs, verts, faces, mtls, materials, LightMapName, type))
            case 'MPK':
                output.geom.append(MeshOut(ob.name, bbox, numUVs, verts, faces, mtls, materials, LightMapName, 0x02))
            case 'PKMDL':
                geom = MeshOut(ob.name, bbox, numUVs, verts, faces, mtls, materials, LightMapName, 0x02)
                bIsOK, geom.weights = GetWeights(arm_obj, ob, srcvt)
                if bIsOK: output.geom.append(geom)
                else: info('\'%s\' is rejected : bad skinning' % ob.name, icon='WARNING')

        ob.to_mesh_clear()
    
    if active_object and org_mode:
        context.view_layer.objects.active = active_object
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode=org_mode)
    
    return output


def GetWeights(arm_obj, mesh_obj, srcvt):    
    bone_names = [bone.name for bone in arm_obj.data.bones]    
    bIsOK = True
    weights = []
    for vert_idx in srcvt:
        influences = []
        for vertex_group in mesh_obj.vertex_groups:
            bone_idx = bone_names.index(vertex_group.name)
            try:
                weight = vertex_group.weight(vert_idx)
                influences.append(SimpleNamespace(bone_idx=bone_idx,weight=weight))
            except: pass
        if len(influences)==0: bIsOK = False
        weights.append(influences)
    return bIsOK, weights


def RemoveDoubles():
    if bpy.context.view_layer.objects.active is not None: bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    for obj in bpy.context.view_layer.objects:
        if obj.type == 'MESH':
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
            bpy.ops.mesh.remove_doubles(threshold = 0.0001, use_sharp_edge_from_normals=True)
            bpy.ops.object.mode_set(mode='OBJECT')
            break
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = None


def dummyMat(geom):
    mat = Material(0, geom.numFaces,
        'notex', UV(0, 0), UV(1, 1),
        '', UV(0, 0), UV(1, 1),
        '', UV(0, 0), UV(1, 1),
        '', UV(0, 0), UV(1, 1))
    geom.nummat = 1
    geom.mat.append(mat)


def BuildMesh(geom):
    # GEOMETRY
    mesh = bpy.data.meshes.new(geom.meshname)
    mesh.vertices.add(geom.numVerts)
    mesh.polygons.add(geom.numFaces)
    mesh.loops.add(geom.numFaces * 3)

    # vertices & normals
    _normals = []
    for vidx, v in enumerate(mesh.vertices):
        vert = geom.verts[vidx]
        v.co.x = vert.x
        v.co.y = vert.y
        v.co.z = vert.z
        _normals.append((vert.nx, vert.ny, vert.nz))

    # faces
    _faces = []
    for f in geom.faces:
        _faces.extend((f.v0, f.v1, f.v2))

    mesh.polygons.foreach_set('loop_start', range(0, geom.numFaces * 3, 3))
    mesh.loops.foreach_set('vertex_index', _faces)
    mesh.transform(tm)

    # MATERIALS
    i = 0
    j = 0
    while i < geom.numFaces:
        if geom.mat[j].size > 0:
            mesh.polygons[i].material_index = j
            geom.mat[j].size -= 1
            i += 1
        else:
            if j < geom.nummat - 1:
                j += 1
            else:
                geom.mat[j].size = 0xFFFF

    # colormap UVs
    mesh.uv_layers.new(name='colormap', do_init=False)
    uvl = mesh.uv_layers.active.data[:]
    for fidx, pl in enumerate(mesh.polygons):
        f = geom.faces[fidx]
        uvl[pl.loop_start + 0].uv = (geom.verts[f.v0].u, geom.verts[f.v0].v)
        uvl[pl.loop_start + 1].uv = (geom.verts[f.v1].u, geom.verts[f.v1].v)
        uvl[pl.loop_start + 2].uv = (geom.verts[f.v2].u, geom.verts[f.v2].v)

    # lightmap UVs
    mesh.uv_layers.new(name='lightmap', do_init=False)
    mesh.uv_layers['lightmap'].active = True
    uvl = mesh.uv_layers.active.data[:]
    for fidx, pl in enumerate(mesh.polygons):
        f = geom.faces[fidx]
        uvl[pl.loop_start + 0].uv = (geom.verts[f.v0].u2, geom.verts[f.v0].v2)
        uvl[pl.loop_start + 1].uv = (geom.verts[f.v1].u2, geom.verts[f.v1].v2)
        uvl[pl.loop_start + 2].uv = (geom.verts[f.v2].u2, geom.verts[f.v2].v2)
    mesh.uv_layers['colormap'].active = True

    # textures
    PBimg = None # pkmdl normal map texture
    if len(geom.normalmap) and geom.nummat == 1: PBimg = read_texture_image(geom.normalmap)
    # lmName = None
    for i in range(geom.nummat):
        bmat = None
        blend = None
        alpha = None
        light = None

        transparents = ['atest', 'decal', 'glass', 'trans']
        trans = re.search(
            r'(?=(' + '|'.join(transparents) + r'))', geom.meshname, re.IGNORECASE
        )

        colorOffset = (geom.mat[i].colorOffset.u, geom.mat[i].colorOffset.v, 0)
        colorScale = (1 / geom.mat[i].colorTiling.u, 1 / geom.mat[i].colorTiling.v, 1)
        blendOffset = (geom.mat[i].blendOffset.u, geom.mat[i].blendOffset.v, 0)
        blendScale = (1 / geom.mat[i].blendTiling.u, 1 / geom.mat[i].blendTiling.v, 1)

        mapto = 'DIFFUSE'
        addtex = True

        if (
            bBlendmaps
            and len(geom.mat[i].blendMapName) > 0
            and len(geom.mat[i].alphaMapName) > 0
            and geom.numchannels == 2
        ):
            mapto = 'BLEND'
            
            blend = read_texture_image(geom.mat[i].blendMapName)
            alpha = read_texture_image(geom.mat[i].alphaMapName)
        
        color = read_texture_image(geom.mat[i].colorMapName)

        if (
            bLightmaps
            and len(geom.mat[i].lightMapName) > 0
            and geom.numchannels == 2
        ):
            light = read_texture_image(geom.mat[i].lightMapName)

        if bool(light) or mapto == 'BLEND':
            matname = 'mtl_' + geom.meshname + '_' + str(i+1)
            bmat = bpy.data.materials.new(matname)
        else:
            texname = ('notex', os.path.basename(geom.mat[i].colorMapName).split('.', 1)[0]) [bool(geom.mat[i].colorMapName)]
            matname = 'mtl_' + texname
            mtl = mtl_cache.get(matname)
            if mtl is not None:
                mesh.materials.append(mtl)  # use existing
                addtex = False
            else:
                bmat = bpy.data.materials.new(matname)
                mtl_cache[matname] = bmat

        # lmName = (lmName,geom.mat[i].lightMapName)[bool(geom.mat[i].lightMapName)]

        if addtex:
            bmat.use_nodes = True
            wrapper = PrincipledBSDFWrapper(bmat, is_readonly=False)

            add_texture_to_material(
                color,
                blend,
                alpha,
                light,
                PBimg,
                trans,
                wrapper,
                colorOffset,
                colorScale,
                blendOffset,
                blendScale,
                mapto,
            )
            bmat.use_backface_culling = True
            mesh.materials.append(bmat)

    if geom.numchannels < 2:
        lm = mesh.uv_layers['lightmap']
        mesh.uv_layers.remove(lm)

    # FINISH UP
    mesh.validate(clean_customdata=False)
    mesh.update()

    mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
    if not re.search(r'(?=(' + '|'.join(zone) + r'))', geom.meshname, re.IGNORECASE) and geom.type == 0x02:
        mesh.normals_split_custom_set_from_vertices(_normals)

    # COLLECTIONS
    ob = bpy.data.objects.new(geom.meshname, mesh)
    if re.search(r'(?=(' + '|'.join(zone) + r'))', geom.meshname, re.IGNORECASE) or geom.type != 0x02:
        try:
            col = bpy.data.collections['___zone___']
            col.objects.link(ob)
        except:
            col = bpy.data.collections.new('___zone___')
            bpy.context.scene.collection.children.link(col)
            col.objects.link(ob)
    # elif bool(lmName) and geom.numchannels == 2:
        # colname = os.path.basename(lmName).split('.', 1)[0]
    # note: PainEngine only considers the first lightmap
    elif len(geom.mat[0].lightMapName) > 0 and geom.numchannels == 2:
        colname = os.path.basename(geom.mat[0].lightMapName).split('.', 1)[0]
        try:
            col = bpy.data.collections[colname]
            col.objects.link(ob)
        except:
            col = bpy.data.collections.new(colname)
            bpy.context.scene.collection.children.link(col)
            col.objects.link(ob)
    elif geom.numchannels == 1:
        try:
            col = bpy.data.collections['___1UVs___']
            col.objects.link(ob)
        except:
            col = bpy.data.collections.new('___1UVs___')
            bpy.context.scene.collection.children.link(col)
            col.objects.link(ob)
    else:
        try:
            col = bpy.data.collections['___noLightMap___']
            col.objects.link(ob)
        except:
            col = bpy.data.collections.new('___noLightMap___')
            bpy.context.scene.collection.children.link(col)
            col.objects.link(ob)
    return ob


SZ_SHORT = struct.calcsize('H')
SZ_INT = struct.calcsize('I')
SZ_FLOAT = struct.calcsize('f')


def readString(file):
    strlen = read_long(file)
    outstring = file.read(strlen)
    return outstring[:-1].decode('iso-8859-1')


def read_short(file):
    temp_data = file.read(SZ_SHORT)
    return struct.unpack('<H', temp_data)[0]


def read_long(file):
    temp_data = file.read(SZ_INT)
    return struct.unpack('<I', temp_data)[0]


def read_float(file):
    temp_data = file.read(SZ_FLOAT)
    return struct.unpack('<f', temp_data)[0]


def read_texture_image(filepath):
    basename = os.path.basename(filepath).split('.', 1)[0]
    if not len(basename):
        basename = 'notex'
    image = image_cache.get(basename)
    if image is not None:
        return image
    image = image_utils.load_image(
        basename + '.dds',
        dirname=dirname,
        place_holder=False,
        recursive=True,
    )
    if image is None:
        image = image_utils.load_image(
        basename + '.tga',
        dirname=dirname,
        place_holder=False,
        recursive=True,
        )
    if image is None:
        image = image_utils.load_image(
        basename + '.bmp',
        dirname=dirname,
        place_holder=False,
        recursive=True,
        )
    # set the 'dds' placeholder if no texture found
    if image is None:
        image = image_utils.load_image(
        basename + '.dds',
        dirname=dirname,
        place_holder=True,
        recursive=False,
        )
    image_cache[basename] = image
    return image


def add_texture_to_material(
    color,
    blend,
    alpha,
    light,
    PBimg,
    trans,
    wrapper,
    colorOffset,
    colorScale,
    blendOffset,
    blendScale,
    mapto,
):
    shader = wrapper.node_principled_bsdf
    nodetree = wrapper.material.node_tree
    shader.location = (600, 0)
    nodes = nodetree.nodes
    links = nodetree.links
    
    img_wrap = wrapper.base_color_texture
    img_wrap.image = color
    img_wrap.extension = 'REPEAT'

    mixer = None

    if mapto == 'BLEND':
        # color
        mapping = nodes.new(type='ShaderNodeMapping')
        wrapper._grid_to_location(-2, 0, dst_node=mapping, ref_node=shader)
        mapping.vector_type = 'TEXTURE'
        mapping.inputs['Location'].default_value[0] = colorOffset[0]
        mapping.inputs['Location'].default_value[1] = colorOffset[1]
        mapping.inputs['Scale'].default_value[0] = colorScale[0]
        mapping.inputs['Scale'].default_value[1] = colorScale[1]
        links.new(mapping.outputs['Vector'], img_wrap.node_image.inputs['Vector'])
        uv_map_node = nodes.new(type='ShaderNodeUVMap')
        uv_map_node.uv_map = 'colormap'
        links.new(uv_map_node.outputs['UV'], mapping.inputs['Vector'])
        wrapper._grid_to_location(-3, 0, dst_node=uv_map_node, ref_node=shader)
        # blend
        blendMap = nodes.new(type='ShaderNodeTexImage')
        wrapper._grid_to_location(-1, -1.2, dst_node=blendMap, ref_node=shader)
        blendMap.image = blend
        blendMap.extension = 'REPEAT'
        mapping = nodes.new(type='ShaderNodeMapping')
        wrapper._grid_to_location(-2, -1.2, dst_node=mapping, ref_node=shader)
        mapping.vector_type = 'TEXTURE'
        mapping.inputs['Location'].default_value[0] = blendOffset[0]
        mapping.inputs['Location'].default_value[1] = blendOffset[1]
        mapping.inputs['Scale'].default_value[0] = blendScale[0]
        mapping.inputs['Scale'].default_value[1] = blendScale[1]
        links.new(uv_map_node.outputs['UV'], mapping.inputs['Vector'])
        links.new(mapping.outputs['Vector'], blendMap.inputs['Vector'])
        # mask
        alphaMap = nodes.new(type='ShaderNodeTexImage')
        wrapper._grid_to_location(-1, 1.2, dst_node=alphaMap, ref_node=shader)
        alphaMap.image = alpha
        alphaMap.extension = 'REPEAT'
        uv_map_node = nodes.new(type='ShaderNodeUVMap')
        wrapper._grid_to_location(-2, 1.2, dst_node=uv_map_node, ref_node=shader)
        uv_map_node.uv_map = 'lightmap'
        links.new(uv_map_node.outputs['UV'], alphaMap.inputs['Vector'])
        # mix
        mixer = nodes.new(type='ShaderNodeMixRGB')
        wrapper._grid_to_location(0.4, -0.075, dst_node=mixer, ref_node=shader)
        links.new(alphaMap.outputs['Color'], mixer.inputs['Fac'])
        links.new(img_wrap.node_image.outputs['Color'], mixer.inputs['Color1'])
        links.new(blendMap.outputs['Color'], mixer.inputs['Color2'])
        links.new(mixer.outputs['Color'], shader.inputs['Base Color'])
    elif mapto == 'DIFFUSE':
        if trans:
            for node in nodes:
                if node.type == 'TEX_IMAGE':
                    links.new(node.outputs['Alpha'], shader.inputs['Alpha'])
                    wrapper.material.blend_method = 'HASHED'

    if bool(light):
        lightMap = nodes.new(type='ShaderNodeTexImage')
        lightMap.image = light
        lightMap.extension = 'REPEAT'
        uv_map_node = nodes.new(type='ShaderNodeUVMap')
        uv_map_node.uv_map = 'lightmap'
        links.new(uv_map_node.outputs['UV'], lightMap.inputs['Vector'])

        mixcolor = nodes.new(type='ShaderNodeMixRGB')
        wrapper._grid_to_location(0.4, -1.55, dst_node=mixcolor, ref_node=shader)
        mixcolor.blend_type = 'COLOR'
        mixcolor.inputs['Fac'].default_value = 1.0
        links.new(lightMap.outputs['Color'], mixcolor.inputs['Color1'])
        links.new(lightMap.outputs['Alpha'], mixcolor.inputs['Color2'])

        multiplier = nodes.new(type='ShaderNodeMixRGB')
        wrapper._grid_to_location(1.2, -0.84, dst_node=multiplier, ref_node=shader)
        multiplier.blend_type = 'MULTIPLY'
        multiplier.inputs['Fac'].default_value = 0.995
        if mapto == 'BLEND':
            wrapper._grid_to_location(-1, -2.4, dst_node=lightMap, ref_node=shader)
            wrapper._grid_to_location(-2, -2.4, dst_node=uv_map_node, ref_node=shader)
            links.new(mixer.outputs['Color'], multiplier.inputs['Color1'])
        else:
            wrapper._grid_to_location(-1, -1.2, dst_node=lightMap, ref_node=shader)   
            wrapper._grid_to_location(-2, -1.2, dst_node=uv_map_node, ref_node=shader)
            links.new(img_wrap.node_image.outputs['Color'], multiplier.inputs['Color1'])
        links.new(mixcolor.outputs['Color'], multiplier.inputs['Color2'])
        links.new(multiplier.outputs['Color'], shader.inputs['Emission Color'])
        shader.inputs["Emission Strength"].default_value = 6.0

    if bool(PBimg):
        NormalMap = nodes.new(type='ShaderNodeNormalMap')
        NormalMap.space = 'OBJECT'
        wrapper._grid_to_location(1.2, -0.5, dst_node=NormalMap, ref_node=shader)
        links.new(NormalMap.outputs['Normal'], shader.inputs['Normal'])
        
        normal = nodes.new(type='ShaderNodeTexImage')
        normal.image = PBimg
        normal.image.colorspace_settings.name = 'Non-Color'
        normal.extension = 'CLIP'
        wrapper._grid_to_location(0.1, -0.8, dst_node=normal, ref_node=shader)
        links.new(normal.outputs['Color'], NormalMap.inputs['Color'])

    shader.location = (1200, 0)
    wrapper._grid_to_location(1, 0, dst_node=wrapper.node_out, ref_node=shader)