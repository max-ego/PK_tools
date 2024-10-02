import io
import os
import bpy
import struct
import array
import mathutils
import re
from bpy_extras import image_utils
from bpy_extras.node_shader_utils import PrincipledBSDFWrapper
from dataclasses import dataclass


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


def load(operator, context, filepath=""):

    load_mpk(filepath, context)

    return {'FINISHED'}


def load_mpk(filepath, context):

    print("importing MPK: %r..." % (filepath), end="")

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

    file = open(filepath, 'rb')

    try:
        read_mesh(file)
    except:
        MessageBox('something went wrong!', title='oops', icon='ERROR')

    file.close()


def read_mesh(file):
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
        geom = Mesh('', 0, 0, [], 0, [], 0, [])
        CacheMesh(file, addr[i] + 4, geom)
        BuildMesh(geom)

    try:
        col = bpy.data.collections['___zone___']
        col.hide_viewport = True
    except:
        pass


def CacheMesh(file, addr, geom):
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
        matname = 'mtl_' + geom.meshname + '_' + str(i+1)

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

        if (
            len(geom.mat[i].blendMapName) > 0
            and len(geom.mat[i].alphaMapName) > 0
            and geom.numchannels == 2
        ):
            mapto = 'BLEND'
            
            blend = read_texture_image(geom.mat[i].blendMapName)
            alpha = read_texture_image(geom.mat[i].alphaMapName)
        else:
            mapto = 'DIFFUSE'
        
        color = read_texture_image(geom.mat[i].colorMapName)
        bmat = bpy.data.materials.new(matname)

        if (
            len(geom.mat[i].lightMapName) > 0
            and geom.numchannels == 2
        ):
            light = read_texture_image(geom.mat[i].lightMapName)
        
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
    mesh.normals_split_custom_set_from_vertices(_normals)

    # COLLECTIONS
    ob = bpy.data.objects.new(geom.meshname, mesh)

    zone = [
        'antyp',
        'barrier',
        'death',
        'ice',
        'ladderzone',
        'monster',
        'physdest',
        'portal',
        'volfog',
        'vollight',
        'zone',
    ]
    if re.search(r'(?=(' + '|'.join(zone) + r'))', geom.meshname, re.IGNORECASE):
        try:
            col = bpy.data.collections['___zone___']
            col.objects.link(ob)
        except:
            col = bpy.data.collections.new('___zone___')
            bpy.context.scene.collection.children.link(col)
            col.objects.link(ob)
    elif len(geom.mat[i].lightMapName) > 0 and geom.numchannels == 2:
        try:
            col = bpy.data.collections[geom.mat[i].lightMapName]
            col.objects.link(ob)
        except:
            col = bpy.data.collections.new(geom.mat[i].lightMapName)
            bpy.context.scene.collection.children.link(col)
            col.objects.link(ob)
        ob.select_set(True)
    else:
        try:
            col = bpy.data.collections['___noLightMap___']
            col.objects.link(ob)
        except:
            col = bpy.data.collections.new('___noLightMap___')
            bpy.context.scene.collection.children.link(col)
            col.objects.link(ob)
        ob.select_set(True)


SZ_FLOAT = struct.calcsize('f')
SZ_U_INT = struct.calcsize('I')
SZ_U_SHORT = struct.calcsize('H')


def readString(file):
    strlen = read_long(file)
    outstring = file.read(strlen)
    return outstring[:-1].decode('utf-8')


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
    basename = os.path.basename(filepath)
    if not len(basename):
        basename = 'notex'
    image = image_cache.get(basename)
    if image is not None:
        return image
    image = image_utils.load_image(
        basename + '.dds',
        dirname=dirname,
        place_holder=True,
        recursive=True,
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

    if light is not None:
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


def MessageBox(message='', title='Message Box', icon='INFO'):
    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)
