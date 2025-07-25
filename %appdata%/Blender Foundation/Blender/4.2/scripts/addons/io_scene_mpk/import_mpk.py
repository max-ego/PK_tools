import array
import bpy
import io
import mathutils
import os
import re
import struct
import time
from bpy_extras import image_utils
from bpy_extras.node_shader_utils import PrincipledBSDFWrapper
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Mesh:
    meshname: str
    numchannels: int
    numVerts: int
    verts: []
    numFaces: int
    faces: []
    nummat: int
    mat: []

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


zone = [
    'antyp',
    'barrier',
    'monster',
    'portal',
    'volfog',
    'vollight',
    'zone',
]


def load(operator, context, filepath='', use_lightmaps=True, use_blendmaps=True, remove_doubles=True):

    global filetype; filetype = Path(filepath).suffix.split('.')[-1].upper()

    global info

    def info(msg='', icon='INFO'): operator.report({icon}, f'{filetype} Import : {msg}')

    load_mpk(filepath, context, use_lightmaps, use_blendmaps, remove_doubles)

    return {'FINISHED'}


def load_mpk(filepath, context, use_lightmaps, use_blendmaps, remove_doubles):

    if bpy.ops.object.select_all.poll():
        bpy.ops.object.select_all(action='DESELECT')

    measure = 1.0  # default meters
    unit_length = context.scene.unit_settings.length_unit
    if unit_length == 'MILES':
        measure = 1609.344
    elif unit_length == 'KILOMETERS':
        measure = 1000.0
    elif unit_length == 'FEET':
        measure = 0.3048
    elif unit_length == 'INCHES':
        measure = 0.0254
    elif unit_length == 'CENTIMETERS':
        measure = 0.01
    elif unit_length == 'MILLIMETERS':
        measure = 0.001
    elif unit_length == 'THOU':
        measure = 0.0000254
    elif unit_length == 'MICROMETERS':
        measure = 0.000001

    global tm
    tm = mathutils.Matrix.Scale(measure, 4)

    global bLightmaps
    bLightmaps = use_lightmaps

    global bBlendmaps
    bBlendmaps = use_blendmaps

    global bRemoveDoubles
    bRemoveDoubles = remove_doubles

    try:
        file = open(filepath, 'rb')
    except:
        info('no such file: \'' + filepath + '\'', icon='ERROR')
        return

    print(f'importing {filetype}: \'{filepath}\'...')

    duration = time.time()
    context.window.cursor_set('WAIT')

    try:
        match filetype:
            case 'MPK': read_mesh_MPK(file)
            case 'DAT': read_mesh_DAT(file)
        try:
            for ob in bpy.data.collections['___zone___'].all_objects:
                ob.select_set(True)
            bpy.ops.object.shade_flat()
            bpy.ops.object.select_all(action='DESELECT')
        except: pass        
        if bRemoveDoubles: RemoveDoubles()
        
        info('success', icon='INFO')
    except:
        info('something went wrong', icon='ERROR')

    file.close()

    try:
        view_3d = [area for area in bpy.context.window.screen.areas if area.type == 'VIEW_3D'][0]
        with bpy.context.temp_override(area=view_3d):
            bpy.context.space_data.shading.show_backface_culling = True
    except: pass

    context.window.cursor_set('DEFAULT')
    print(f'{filetype} import time: %.2f' % (time.time() - duration))


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


def read_mesh_DAT(file):
    global dirname
    dirname = os.path.dirname(file.name)
    geometry = CacheMeshDAT(file)

    global mtl_cache
    global image_cache
    mtl_cache = {}
    image_cache = {}
    
    for geom in geometry: BuildMesh(geom)


def read_mesh_MPK(file):
    global dirname
    dirname = os.path.dirname(file.name)

    file.seek(-8, io.SEEK_END)
    numobj = read_long(file)

    addr = []
    temp = 0 - (8 + numobj * 4)
    file.seek(temp, io.SEEK_END)
    for i in range(numobj):
        addr.append(read_long(file))

    global mtl_cache
    global image_cache
    mtl_cache = {}
    image_cache = {}
    for i in range(numobj):
        geom = Mesh('', 0, 0, [], 0, [], 0, [], 0x02, 0, 0, 0)
        CacheMeshMPK(file, addr[i] + 4, geom)
        BuildMesh(geom)


def dummyMat(geom):
    mat = Material(0, geom.numFaces,
        'notex', UV(0, 0), UV(1, 1),
        '', UV(0, 0), UV(1, 1),
        '', UV(0, 0), UV(1, 1),
        '', UV(0, 0), UV(1, 1))
    geom.nummat = 1
    geom.mat.append(mat)


def CacheMeshDAT(file):
    pkspc = mathutils.Matrix(( (1,0,0,0),(0,0,-1,0),(0,1,0,0),(0,0,0,0) ))
    file.seek(0, io.SEEK_SET)
    namelist = []
    for i in range(read_long(file)):
        namelist.append(readString(file))

    numobj = read_long(file)
    geometry = []
    for i in range(numobj):
        geometry.append(Mesh('', 0, 0, [], 0, [], 0, [], 0x02, 0, 0, 0))
        temp = read_long(file) # 00 00 00 00
        geometry[i].type = read_long(file)
        index = read_long(file)
        geometry[i].index = index
        geometry[i].meshname = namelist[index]
        geometry[i].size = read_long(file)
        geometry[i].offset = read_long(file)

    for i in range(numobj):
        file.seek(geometry[i].offset, io.SEEK_SET)
        if geometry[i].index == 0:
            geometry[i].meshname = readString(file)
            if   geometry[i].type == 1: # reg
                geometry[i].type = 0x02;
            elif geometry[i].type == 2: # zone
                geometry[i].type = 0x04;
            elif geometry[i].type == 3: # portal
                geometry[i].type = 0x08;
            elif geometry[i].type == 4: # antyp
                geometry[i].type = 0x10;
        else:
            readString(file)

        if geometry[i].type == 0x02:
            geometry[i].numchannels = 1 if read_long(file) & 0x0400 else 2

        # ANTYP : is not used in any of the original files
        if geometry[i].type == 0x10:
            dummyMat(geometry[i])
            geometry[i].numchannels = 1
            
            geometry[i].numVerts = read_long(file)
            for ii in range(geometry[i].numVerts):
                pt = pkspc @ mathutils.Vector((read_float(file),read_float(file),read_float(file)))
                geometry[i].verts.append(Vertex(pt.x, pt.y, pt.z, 0,0,0,0,0,0,0))

            geometry[i].numFaces = int(read_long(file) / 3)
            for ii in range(geometry[i].numFaces):
                v0, v1, v2 = read_short(file), read_short(file), read_short(file)
                geometry[i].faces.append(Face(v0, v2, v1))
            continue

        # bounding box
        bbox = [
            pkspc @ mathutils.Vector((read_float(file),read_float(file),read_float(file))),
            pkspc @ mathutils.Vector((read_float(file),read_float(file),read_float(file))),
            ]

        # ZONE
        if geometry[i].type == 0x04:
            dummyMat(geometry[i])
            geometry[i].numchannels = 1

            geometry[i].numVerts = 8

            for ii in range(geometry[i].numVerts):
                geometry[i].verts.append(Vertex(
                bbox[int(ii>>0&1)].x, bbox[int(ii>>1&1)].y, bbox[int(ii>>2&1)].z,
                0,0,0,0,0,0,0))

            geometry[i].numFaces = 12

            geometry[i].faces.append(Face(3,0,1))
            geometry[i].faces.append(Face(0,3,2))
            geometry[i].faces.append(Face(7,2,3))
            geometry[i].faces.append(Face(2,7,6))
            geometry[i].faces.append(Face(5,6,7))
            geometry[i].faces.append(Face(6,5,4))
            geometry[i].faces.append(Face(1,4,5))
            geometry[i].faces.append(Face(4,1,0))

            geometry[i].faces.append(Face(6,0,2))
            geometry[i].faces.append(Face(0,6,4))
            geometry[i].faces.append(Face(5,3,1))
            geometry[i].faces.append(Face(3,5,7))

            continue

        # PORTAL
        if geometry[i].type == 0x08:
            dummyMat(geometry[i])
            geometry[i].numchannels = 1

            geometry[i].numFaces = 2
            geometry[i].faces.append(Face(0, 2, 1))
            geometry[i].faces.append(Face(0, 3, 2))

            geometry[i].numVerts = read_long(file)
            for ii in range(geometry[i].numVerts):
                pt = pkspc @ mathutils.Vector((read_float(file),read_float(file),read_float(file)))
                vert = Vertex(pt.x, pt.y, pt.z, 0,0,0,0,0,0,0)
                geometry[i].verts.append(vert)
            continue

        # matrix
        file.seek(64, io.SEEK_CUR)

        # 00 00 00 00 - ?
        file.seek(4, io.SEEK_CUR)

        # materials
        lightmap = Path(readString(file)).stem
        notex = readString(file)
        geometry[i].nummat = read_long(file)
        for ii in range(geometry[i].nummat):
            colormap = Path(readString(file)).stem
            offset = read_long(file)
            size = read_long(file)
            mat = Material(offset, size,
                colormap, UV(0, 0), UV(1, 1),
                lightmap, UV(0, 0), UV(1, 1),
                '', UV(0, 0), UV(1, 1),
                '', UV(0, 0), UV(1, 1),
            )
            geometry[i].mat.append(mat)

        # dummy material
        if geometry[i].nummat == 0: dummyMat(geometry[i])

        # faces
        num_verts = read_long(file)
        if (num_verts % 3) == 0:
            geometry[i].numFaces = int(num_verts / 3)
            for ii in range(geometry[i].numFaces):
                v0, v1, v2 = read_short(file), read_short(file), read_short(file)
                geometry[i].faces.append(Face(v0, v2, v1))
        else:
            file.seek(SZ_U_SHORT*num_verts, io.SEEK_CUR)

        # triangle strip
        num_verts = read_long(file)
        if num_verts > 0:
            faces = []
            vl = [None for ii in range(num_verts)] #vertlist
            k = 0
            offset = geometry[i].mat[k].offset;
            length = geometry[i].mat[k].size + 2;
            for j in range(num_verts):
                if j == length:
                    k += 1
                    try:
                        offset = geometry[i].mat[k].offset
                        length = geometry[i].mat[k].size + 2
                    except: break

                vl[j] = read_short(file)
                if (vl[j - 2] == vl[j - 1] or vl[j - 1] == vl[j - 0] or vl[j - 2] == vl[j - 0]) or j < offset + 2 or j > length: continue

                face = Face(0, 0, 0)
                if (j - offset) % 2 == 0:
                    face.v0 = vl[j - 0]
                    face.v1 = vl[j - 1]
                    face.v2 = vl[j - 2]
                else:
                    face.v0 = vl[j - 2]
                    face.v1 = vl[j - 1]
                    face.v2 = vl[j - 0]
                faces.append(face)
            geometry[i].numFaces = len(faces)
            geometry[i].faces = faces

        # coords
        geometry[i].numVerts = read_long(file)
        for ii in range(geometry[i].numVerts):
            vert = Vertex(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            vert.x = read_float(file)
            vert.z = read_float(file)
            vert.y = -read_float(file)

            if geometry[i].numchannels == 2:
                file.seek(4, io.SEEK_CUR)  # 00 00 00 00
                vert.u = read_float(file)
                vert.v = 1 - read_float(file)
                vert.u2 = read_float(file)
                vert.v2 = 1 - read_float(file)
            else:
                vert.nx = read_float(file)
                vert.nz = read_float(file)
                vert.ny = -read_float(file)
                vert.u = read_float(file)
                vert.v = 1 - read_float(file)
            geometry[i].verts.append(vert)
        # normals (if the 2nd UV channel is present)
        nrmls = read_long(file)
        for ii in range(nrmls):
            geometry[i].verts[ii].nx = read_float(file)
            geometry[i].verts[ii].nz = read_float(file)
            geometry[i].verts[ii].ny = -read_float(file)

        # vertex index out of range fix (2domCALY.dat)
        for ii in range(geometry[i].numFaces):
            face = geometry[i].faces[ii]
            if face.v0 > geometry[i].numVerts: face.v0 = 0
            if face.v1 > geometry[i].numVerts: face.v1 = 0
            if face.v2 > geometry[i].numVerts: face.v2 = 0

        # tangents
        temp = read_long(file)
        for ii in range(temp):
            file.read(8*SZ_FLOAT)

    return geometry


def CacheMeshMPK(file, addr, geom):
    file.seek(addr, io.SEEK_SET)
    geom.meshname = readString(file)

    # skip matrix
    file.seek(64, io.SEEK_CUR)

    # vertices
    geom.numchannels = read_long(file)
    geom.numVerts = read_long(file)

    for i in range(geom.numVerts):
        vert = Vertex(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        vert.x = read_float(file)
        vert.z = read_float(file)
        vert.y = -read_float(file)

        if geom.numchannels == 2:
            file.seek(4, io.SEEK_CUR)  # 00 00 00 00
            vert.u = read_float(file)
            vert.v = 1 - read_float(file)
            vert.u2 = read_float(file)
            vert.v2 = 1 - read_float(file)
        else:
            vert.nx = read_float(file)
            vert.nz = read_float(file)
            vert.ny = -read_float(file)
            vert.u = read_float(file)
            vert.v = 1 - read_float(file)
        geom.verts.append(vert)

    # normals (if the 2nd UV channel is present)
    nrmls = read_long(file)
    for i in range(nrmls):
        geom.verts[i].nx = read_float(file)
        geom.verts[i].nz = read_float(file)
        geom.verts[i].ny = -read_float(file)

    # skip bounding box
    file.seek(24, io.SEEK_CUR)

    # faces
    geom.numFaces = int(read_long(file) / 3)
    for i in range(geom.numFaces):
        face = Face(0, 0, 0)
        face.v0 = read_short(file)
        face.v2 = read_short(file)
        face.v1 = read_short(file)
        geom.faces.append(face)

    # materials
    geom.nummat = read_long(file)
    for i in range(geom.nummat):
        mat = Material(
            read_short(file),
            read_short(file),
            readString(file),
            UV(read_float(file), read_float(file)),
            UV(read_float(file), read_float(file)),
            readString(file),
            UV(read_float(file), read_float(file)),
            UV(read_float(file), read_float(file)),
            readString(file),
            UV(read_float(file), read_float(file)),
            UV(read_float(file), read_float(file)),
            readString(file),
            UV(read_float(file), read_float(file)),
            UV(read_float(file), read_float(file)),
        )
        geom.mat.append(mat)

    # dummy material
    if geom.nummat == 0: dummyMat(geom)


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

        if addtex:
            wrapper = PrincipledBSDFWrapper(bmat, is_readonly=False, use_nodes=True)

            add_texture_to_material(
                color,
                blend,
                alpha,
                light,
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


SZ_FLOAT = struct.calcsize('f')
SZ_U_INT = struct.calcsize('I')
SZ_U_SHORT = struct.calcsize('H')


def readString(file):
    strlen = read_long(file)
    outstring = file.read(strlen)
    return outstring[:-1].decode('iso-8859-1')


def read_short(file):
    temp_data = file.read(SZ_U_SHORT)
    return struct.unpack('<H', temp_data)[0]


def read_long(file):
    temp_data = file.read(SZ_U_INT)
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
    # set the 'dds' placeholder if no textures were found
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

    shader.location = (1200, 0)
    wrapper._grid_to_location(1, 0, dst_node=wrapper.node_out, ref_node=shader)
