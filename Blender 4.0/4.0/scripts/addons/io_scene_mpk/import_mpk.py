import io
import os
import bpy
import struct
import array
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
    nx:float
    ny:float
    nz:float
    u: float
    v: float
    u2:float
    v2:float

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

    file = open(filepath, 'rb')

    try:
        read_mesh(file)
    except:
        MessageBox('something went wrong!', title = 'oops', icon = 'ERROR')

    file.close()

def read_mesh(file):
    global dirname
    dirname = os.path.dirname(file.name)
    file.seek(-8, io.SEEK_END)
    numobj = read_long(file)
    
    addr = []
    temp = 0 - (8 + numobj*4);
    file.seek(temp,io.SEEK_END)
    for i in range(numobj):
        addr.append(read_long(file))
    
    global mtl_cache
    mtl_cache = {}
    for i in range(numobj):
        geom = Mesh('',0,0,[],0,[],0,[])
        CacheMesh(file, addr[i]+4, geom)
        BuildMesh(geom)

#    try:
#        col = bpy.data.collections["___zone___"]
#        col.hide_viewport = True
#    except:
#        pass
        
        
def CacheMesh(file, addr, geom):
    file.seek(addr, io.SEEK_SET)
    geom.meshname = readString(file)
    
    file.seek(64, io.SEEK_CUR); #skip matrix
    
    # vertices
    geom.numchannels = read_long(file)
    geom.numVerts = read_long(file)

    for i in range(geom.numVerts):
        vert = Vertex(0,0,0,0,0,0,0,0,0,0)
        vert.x = read_float(file)
        vert.z = read_float(file)
        vert.y = -read_float(file)
        
        if geom.numchannels == 2:
            file.seek(4, io.SEEK_CUR); #00 00 00 00
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
        
    # normals (if 2nd UV channel is presented)
    nrmls = read_long(file)
    for i in range(nrmls):
        geom.verts[i].nx = read_float(file)
        geom.verts[i].nz = read_float(file)
        geom.verts[i].ny = -read_float(file)
            
    file.seek(24, io.SEEK_CUR); #skip bounding box

    # faces
    geom.numFaces = int(read_long(file)/3)
    for i in range(geom.numFaces):
        face = Face(0,0,0)
        face.v0 = read_short(file)
        face.v2 = read_short(file)
        face.v1 = read_short(file)
        geom.faces.append(face)
    
    # materials
    geom.nummat = read_long(file)
    for i in range(geom.nummat):
        mat = Material(
        0,0,
        "",UV(0,0),UV(1,1),
        "",UV(0,0),UV(1,1),
        "",UV(0,0),UV(1,1),
        "",UV(0,0),UV(1,1)
        )
        mat.offset = read_short(file)
        mat.size = read_short(file)
        mat.colorMapName = readString(file)
        mat.colorOffset = UV(read_float(file),read_float(file))
        mat.colorTiling = UV(read_float(file),read_float(file))
        mat.lightMapName = readString(file)
        mat.lightOffset = UV(read_float(file),read_float(file))
        mat.lightTiling = UV(read_float(file),read_float(file))
        mat.blendMapName = readString(file)
        mat.blendOffset = UV(read_float(file),read_float(file))
        mat.blendTiling = UV(read_float(file),read_float(file))
        mat.alphaMapName = readString(file)
        mat.alphaOffset = UV(read_float(file),read_float(file))
        mat.alphaTiling = UV(read_float(file),read_float(file))
        geom.mat.append(mat)
    

def BuildMesh(geom):
    mesh = bpy.data.meshes.new(geom.meshname)
    mesh.vertices.add(geom.numVerts)
    mesh.polygons.add(geom.numFaces)
    mesh.loops.add(geom.numFaces*3)
    mesh.create_normals_split()
    
    # vertices
    for vidx, v in enumerate(mesh.vertices):
        v.co.x = geom.verts[vidx].x
        v.co.y = geom.verts[vidx].y
        v.co.z = geom.verts[vidx].z

    # faces & normals
    _faces = []
    _normals = []
    for f in geom.faces:
        _faces.extend((f.v0, f.v1, f.v2))
        v = geom.verts[f.v0]
        _normals.extend((v.nx, v.ny, v.nz))
        v = geom.verts[f.v1]
        _normals.extend((v.nx, v.ny, v.nz))
        v = geom.verts[f.v2]
        _normals.extend((v.nx, v.ny, v.nz))
    
    mesh.polygons.foreach_set("loop_start", range(0, geom.numFaces * 3, 3))
    mesh.loops.foreach_set("vertex_index", _faces)
    mesh.loops.foreach_set("normal", _normals)

    # materials
    i = 0
    j = 0
    while i < geom.numFaces:
        if geom.mat[j].size > 0:
            mesh.polygons[i].material_index = j
            geom.mat[j].size -= 1
            i += 1
        else:
            if j < geom.nummat-1:
                j += 1;
            else:
                geom.mat[j].size = 0xffff
    
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
    
    mesh.validate(clean_customdata=False)
    mesh.update()

    for i in range(geom.nummat):
        matname = "mtl_" + geom.mat[i].colorMapName
        
        bmat = None
        blend = None
        alpha = None
        mapto = 'DIFFUSE'
        addtex = True
        transparents = ['atest','decal','glass','trans']
        trans = re.search(r"(?=("+'|'.join(transparents)+r"))", geom.meshname, re.IGNORECASE)
        
        colorOffset = (geom.mat[i].colorOffset.u, geom.mat[i].colorOffset.v, 0)
        colorScale  = (1/geom.mat[i].colorTiling.u, 1/geom.mat[i].colorTiling.v, 1)
        blendOffset = (geom.mat[i].blendOffset.u, geom.mat[i].blendOffset.v, 0)
        blendScale  = (1/geom.mat[i].blendTiling.u, 1/geom.mat[i].blendTiling.v, 1)
        uv_map = mesh.uv_layers['lightmap'].name
        if len(geom.mat[i].blendMapName) > 0 and geom.numchannels == 2:
            mapto = 'BLEND'
        
            color = image_utils.load_image(
            geom.mat[i].colorMapName + ".dds",
            dirname=dirname,
            place_holder=True,
            recursive=True,
            )
            
            blend = image_utils.load_image(
            geom.mat[i].blendMapName + ".dds",
            dirname=dirname,
            place_holder=True,
            recursive=True,
            )
        
            alpha = image_utils.load_image(
            geom.mat[i].alphaMapName + ".dds",
            dirname=dirname,
            place_holder=True,
            recursive=True,
            )
            
            bmat = bpy.data.materials.new(matname)
        else:
            mapto = 'DIFFUSE'
            
            mtl = mtl_cache.get(matname)
            if mtl is not None:
                mesh.materials.append(mtl) # use existing
                addtex = False
            else:            
                color = image_utils.load_image(
                geom.mat[i].colorMapName + ".dds",
                dirname=dirname,
                place_holder=True,
                recursive=True,
                )
                bmat = bpy.data.materials.new(matname)
                mtl_cache[matname] = bmat
        
        if addtex:
            wrapper = PrincipledBSDFWrapper(bmat, is_readonly=False, use_nodes=True)
                
            add_texture_to_material(color,blend,alpha,trans,wrapper,
            colorOffset,colorScale,blendOffset,blendScale,mapto,uv_map)

            bmat.use_backface_culling = True            
            mesh.materials.append(bmat)
    
    # finish up    
    clnors = array.array('f', [0.0] * (len(mesh.loops) * 3))
    mesh.loops.foreach_get("normal", clnors)
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    mesh.normals_split_custom_set(tuple(zip(*(iter(clnors),) * 3)))
    mesh.use_auto_smooth = True

    ob = bpy.data.objects.new(geom.meshname, mesh)

    zone = ['antyp','barrier','death','ladderzone','monster','physdest','portal','volfog','volligh','zone']
    if re.search(r"(?=("+'|'.join(zone)+r"))", geom.meshname, re.IGNORECASE):
        try:
            col = bpy.data.collections["___zone___"]
            col.objects.link(ob)
        except:
            col = bpy.data.collections.new("___zone___")
            bpy.context.scene.collection.children.link(col)
            col.objects.link(ob)
    else:        
        try:
            col = bpy.data.collections[geom.mat[i].lightMapName]
            col.objects.link(ob)
        except:
            col = bpy.data.collections.new(geom.mat[i].lightMapName)
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

def add_texture_to_material(color, blend, alpha, trans, wrapper, 
colorOffset, colorScale, blendOffset, blendScale, mapto, uv_map):
    shader = wrapper.node_principled_bsdf
    nodetree = wrapper.material.node_tree
    shader.location = (-300, 0)
    nodes = nodetree.nodes
    links = nodetree.links

    if mapto == 'BLEND':
        # blend
        blendMap = nodes.new(type='ShaderNodeTexImage')
        blendMap.location = (-300, 300)
        blendMap.image = blend
        blendMap.extension = 'REPEAT'
        mapping = nodes.new('ShaderNodeMapping')
        mapping.location = (-600, 0)
        mapping.vector_type = 'TEXTURE'
        mapping.inputs['Location'].default_value[0] = blendOffset[0]
        mapping.inputs['Location'].default_value[1] = blendOffset[1]
        mapping.inputs['Scale'].default_value[0] = blendScale[0]
        mapping.inputs['Scale'].default_value[1] = blendScale[1]
        uv_node = nodes.new('ShaderNodeTexCoord')
        uv_node.location = (-1200, 0)
        links.new(uv_node.outputs['UV'], mapping.inputs['Vector'])
        links.new(mapping.outputs['Vector'], blendMap.inputs['Vector'])
        # mask
        alphaMap = nodes.new(type='ShaderNodeTexImage')
        alphaMap.location = (-300, 600)
        alphaMap.image = alpha
        alphaMap.extension = 'REPEAT'
        uv_map_node = nodes.new('ShaderNodeUVMap')
        uv_map_node.location = (-600, 600)
        uv_map_node.uv_map = uv_map
        links.new(uv_map_node.outputs[0], alphaMap.inputs[0])
        mixer = nodes.new(type='ShaderNodeMixRGB')
        mixer.label = "Mixer"
        wrapper._grid_to_location(1, 2, dst_node=mixer, ref_node=shader)
        img_wrap = wrapper.base_color_texture
        img_wrap.scale = colorScale
        img_wrap.translation = colorOffset
        links.new(alphaMap.outputs['Color'], mixer.inputs[0])
        links.new(mixer.outputs['Color'], shader.inputs['Base Color'])
        links.new(img_wrap.node_image.outputs['Color'], mixer.inputs[1])
        links.new(blendMap.outputs['Color'], mixer.inputs[2])
    elif mapto == 'DIFFUSE':
        img_wrap = wrapper.base_color_texture
        if trans:
            for node in nodes:
                if node.type == 'TEX_IMAGE':
                    links.new(node.outputs['Alpha'], shader.inputs['Alpha'])
                    wrapper.material.blend_method = 'HASHED'

    img_wrap.image = color
    img_wrap.extension = 'REPEAT'

    shader.location = (300, 300)
    wrapper._grid_to_location(1, 0, dst_node=wrapper.node_out, ref_node=shader)

def MessageBox(message = "", title = "Message Box", icon = 'INFO'):

    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)