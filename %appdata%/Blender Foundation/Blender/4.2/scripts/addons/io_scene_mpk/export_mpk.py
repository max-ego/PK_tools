import array
import bmesh
import bpy
import mathutils
import os
import numpy as np
import re
import struct
import time
import bpy_extras
from bpy_extras.node_shader_utils import PrincipledBSDFWrapper


def load(operator, context, filepath='', use_default=True, use_optimize=False, use_all=True, use_selection=False, use_visible=False, use_sort=False, scale_factor=1.0, global_matrix=None):

    global info

    def info(msg='', icon='INFO'): operator.report({icon}, 'MPK Export : ' + msg)

    global bDefault;   bDefault   = use_default
    global bOptimize;  bOptimize  = use_optimize
    global bAll;       bAll       = use_all
    global bSelection; bSelection = use_selection
    global bVisible;   bVisible   = use_visible
    global bSort;      bSort      = use_sort
    global scale;      scale      = scale_factor

    save_mpk(filepath, context, global_matrix)

    return {'FINISHED'}


def save_mpk(filepath, context, global_matrix):

    try: file = open(filepath, 'wb')
    except:
        info('access denied : \'' + filepath + '\'', icon='ERROR')
        return

    print('exporting MPK: %r...' % filepath)

    duration = time.time()
    context.window.cursor_set('WAIT')

    try:
        meshoffset = doexp(file, context, global_matrix)
        for offset in meshoffset:
            write_long(file, offset)
        write_long(file, len(meshoffset))
        write_long(file, 0xDEADBEEF) # closing
        info('success', icon='INFO')
    except:
        info('something went wrong', icon='ERROR')

    file.close()

    context.window.cursor_set('DEFAULT')
    print('MPK export time: %.2f' % (time.time() - duration))


zone = [
    'antyp',
    'barrier',
    'monster',
    'portal',
    'volfog',
    'vollight',
    'zone',
]


SZ_SHORT = 2
SZ_INT = 4
SZ_FLOAT = 4


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
    }
    if mtl and mtl.use_nodes:
        wrapper = PrincipledBSDFWrapper(mtl)
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


def triangulate_object( mesh ):
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


def ConvertToMPKFaces( mesh, bRound ):
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
            if bDefault:
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
            elif bOptimize:
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
        faces.append(face)
    if bDefault:
        return verts, faces
    elif bOptimize:
        return _map_n_pack(verts), faces


def doexp(file, context, global_matrix):

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
        # Get derived objects
        derived_dict = bpy_extras.io_utils.create_derived_objects(depsgraph, [ob])
        derived = derived_dict.get(ob)

        if derived is None:
            continue

        for ob_derived, mtx in derived:
            if ob.type not in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}:
                continue

            try:
                data = ob_derived.to_mesh()
            except:
                data = None

            if data:
                matrix = global_matrix @ mtx
                data.transform(matrix)
                data.transform(mtx_scale)
                mesh_objects.append((ob_derived, data, matrix))

    if active_object and org_mode:
        context.view_layer.objects.active = active_object
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode=org_mode)

    offset = 0
    meshoffset = []; total = str(len(mesh_objects))
    for ob, mesh, matrix in mesh_objects:
        triangulate_object( mesh )

        bRound = re.search(r'(?=(' + '|'.join(zone) + r'))', ob.name, re.IGNORECASE)
        verts, faces = ConvertToMPKFaces( mesh, bRound )

        if len(verts) == 0 or len(faces) == 0: continue

        if len(verts)>0xffff:
            info('\'%s\' is rejected : too many vertices (> 64K)' % ob.name, icon='WARNING')
            continue
        if len(faces)>0xffff:
            info('\'%s\' is rejected : too many faces (> 64K)' % ob.name, icon='WARNING')
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
                assert(mtl_offset<=0xffff)
                mtl_offset += mtl[0]*3
        except:
            info('\'%s\' is rejected : too many faces' % ob.name, icon='WARNING')
            continue

        materials = ([getMaterial(None)],[])[bool(ob.material_slots)]
        for slot in ob.material_slots:
            mtl = getMaterial(slot.material)
            materials.append(mtl);

        numUVs = 2 if len(mesh.uv_layers) > 1 else 1
        meshoffset.append(offset)

        # mesh entry
        write_long(file,0xDEAFBABE); offset += SZ_INT

        # mesh name
        write_long(file,len(ob.name)+1); offset += SZ_INT
        writeString(file,ob.name); offset += len(ob.name)+1

        # transform matrix
        dummy = struct.pack('<16f', 1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1)
        file.write(dummy); offset += 16 * SZ_FLOAT

        # vertices
        write_long(file,numUVs); offset += SZ_INT
        write_long(file,len(verts)); offset += SZ_INT
        for key in verts:
            file.write(key[0:12])
            if numUVs == 2:
                write_float(file,0)
                file.write(key[24:40])
            else:
                file.write(key[12:32])
            offset += 8 * SZ_FLOAT
        # normals if 2-ch
        if numUVs == 2:
            write_long(file,len(verts)); offset += SZ_INT
            for key in verts:
                file.write(key[12:24])
                offset += 3 * SZ_FLOAT
        else:
            write_long(file,0); offset += SZ_INT

        # bounding box
        pkspc = mathutils.Matrix(( (1,0,0,0),(0,0,-1,0),(0,1,0,0),(0,0,0,0) ))
        bbox_corners = [ob.matrix_world @ mathutils.Vector(corner) for corner in ob.bound_box]
        p1 = bbox_corners[3] @ pkspc
        p2 = bbox_corners[5] @ pkspc
        write_float(file,p1.x); write_float(file,p1.y); write_float(file,p1.z)
        write_float(file,p2.x); write_float(file,p2.y); write_float(file,p2.z)
        offset += 6 * SZ_FLOAT

        # faces
        write_long(file,len(faces)*3); offset += SZ_INT
        for f in faces:
            write_short(file,f[0])
            write_short(file,f[2])
            write_short(file,f[1]); offset += 3 * SZ_SHORT

        # materials
        LightMapName = ''
        if numUVs == 2:
            colls = ob.users_collection
            if colls[0].name != 'Scene Collection':
                LightMapName = colls[0].name
            else:
                LightMapName = ob.name + '_L_0000'

        mtl_offset = 0
        num_mtls = len(mtls)
        write_long(file,num_mtls); offset += SZ_INT
        for i in range(num_mtls):
            write_short(file,mtl_offset); offset += SZ_SHORT
            mtl_len = mtls.get(i)[0]
            mtl_idx = mtls.get(i)[1]
            mtl = materials[mtl_idx]
            mtl_offset += mtl_len * 3
            write_short(file,mtl_len); offset += SZ_SHORT
            # color map : uses 1st UV-channel
            texName = mtl.get('color')
            write_long(file,len(texName)+1); offset += SZ_INT
            writeString(file,texName); offset += len(texName)+1
            mapping = struct.pack('<4f', mtl.get('c_loc')[0], mtl.get('c_loc')[1], mtl.get('c_scl')[0], mtl.get('c_scl')[1])
            file.write(mapping); offset += 4 * SZ_FLOAT
            # light map : uses 2nd UV-channel
            texName = mtl.get('light')
            if texName is None: texName = fname(LightMapName)
            write_long(file,len(texName)+1); offset += SZ_INT
            writeString(file,texName); offset += len(texName)+1
            mapping = struct.pack('<4f', 0, 0, 1, 1)
            file.write(mapping); offset += 4 * SZ_FLOAT
            # blend map : uses 1st UV-channel
            texName = mtl.get('blend')
            write_long(file,len(texName)+1); offset += SZ_INT
            writeString(file,texName); offset += len(texName)+1
            mapping = struct.pack('<4f', mtl.get('b_loc')[0], mtl.get('b_loc')[1], mtl.get('b_scl')[0], mtl.get('b_scl')[1])
            file.write(mapping); offset += 4 * SZ_FLOAT
            # alpha map : uses 2nd UV-channel
            texName = mtl.get('alpha')
            write_long(file,len(texName)+1); offset += SZ_INT
            writeString(file,texName); offset += len(texName)+1
            mapping = struct.pack('<4f', 0, 0, 1, 1)
            file.write(mapping); offset += 4 * SZ_FLOAT

    return meshoffset
