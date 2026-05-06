from .common import *


def strToBytes(name):
    out = bytearray()
    out += struct.pack('<I', len(name))
    out += name.encode('iso-8859-1', 'replace')
    return out


def save_mdl(file, context, global_matrix, params):

    try: arm_obj=[obj for obj in context.scene.objects if obj.type == 'ARMATURE'][0]
    except:
        info('No armature found', icon='WARNING')
        return

    skins = []
    out = bytearray()
    skinname = os.path.basename(file.name).split('.', 1)[0]
    out += strToBytes(skinname + '\x00')
    roots = [b for b in arm_obj.data.bones if b.parent is None]
    # numskels
    out += struct.pack('<H', len(roots))
    # numbones
    out += struct.pack('<I', len(arm_obj.data.bones))
    skel = []
    for bone in arm_obj.data.bones:
        # name
        out += strToBytes(bone.name + '\x00')
        pose_bone = arm_obj.pose.bones[bone.name]
        # parent space matrix 'REST'
        mtx = pose_bone.bone.matrix_local
        if bone.parent != None:
            mtx = pose_bone.parent.bone.matrix_local.inverted() @ mtx
        mtx = pkspc.inverted() @ mtx.transposed() @ pkspc.inverted().transposed()
        flat = [item for row in mtx for item in row]
        out += struct.pack('16f', *flat)
        # numchildren
        out += struct.pack('B', (0,len(bone.children))[bool(bone.children)])

    arm_obj.data.pose_position = 'REST'
    data = getGeometry(file, context, global_matrix, params + (arm_obj,))
    arm_obj.data.pose_position = 'POSE'
    out += struct.pack('<I', len(data.geom))
    for ob in data.geom:
        # name
        out += strToBytes(ob.name + '\x00')
        # MATERIALS
        out += struct.pack('<2I', 0, 0)
        # normal
        texName = ob.materials[0].get('PBimg')
        if len(ob.mtls)==1 and len(texName): out += strToBytes(texName + '\x00')
        else: out += struct.pack('<I', 0)
        # colors
        mtl_offset = 0
        num_mtls = len(ob.mtls)
        out += struct.pack('<I', num_mtls)
        for i in range(num_mtls):
            mtl_len = ob.mtls.get(i)[0]
            mtl_idx = ob.mtls.get(i)[1]
            mtl = ob.materials[mtl_idx]
            texName = mtl.get('color')
            out += strToBytes(texName + '\x00')  # color
            out += struct.pack('<I', mtl_offset) # offset
            out += struct.pack('<I', mtl_len)    # size
            mtl_offset += mtl_len * 3
        # faces
        out += struct.pack('<I', 3*len(ob.faces))
        for f in ob.faces: out += struct.pack('<3H', f[0],f[1],f[2])
        out += struct.pack('<I', 0)
        # vertices
        out += struct.pack('<I', len(ob.verts))
        for key in ob.verts: out += key[0:32]
        out += struct.pack('<2I', 0, 0)
        # skinning
        out += struct.pack('<I', len(ob.weights))
        for influences in ob.weights:
            out += struct.pack('<i', len(influences))
            for influence in influences:
                out += struct.pack('<H', influence.bone_idx)
                out += struct.pack('<f', influence.weight)
    skins.append(strToBytes(skinname + '.pkmdl' + '\x00'))
    skins.append(out)
    skins.append(strToBytes('AnimatedMesh' + '\x00'))

    names = []
    for skin in skins:
        size = struct.unpack('<I', skin[0:4])[0]
        names.append(skin[4:4+size][:-1].decode('iso-8859-1'))
    head = bytearray()
    head += struct.pack('<I', len(names))
    for name in names:
        head += strToBytes(name + '\x00')
    skincount = len(skins)-2
    head += struct.pack('<I', skincount)
    index = 0
    offset = len(head) + 5*SZ_INT*skincount
    for i,skin in enumerate(skins):
        if i in (0,2): continue
        head += struct.pack('<I', 0x00)      # - ?
        head += struct.pack('<I', 0x02)      # type
        head += struct.pack('<I', i)         # index
        head += struct.pack('<I', len(skin)) # size
        head += struct.pack('<I', offset)    # offset
        offset += len(skin)
    file.write(head)
    for i,skin in enumerate(skins):
        if i in (0,2): continue
        file.write(skin)


def save_ani(file, context):

    try: arm_obj=[obj for obj in context.scene.objects if obj.type == 'ARMATURE'][0]
    except:
        info('No armature found', icon='WARNING')
        return

    fcurves = None
    anim_data = arm_obj.animation_data
    try:     # blender 4
        fcurves = arm_obj.animation_data.action.fcurves
    except Exception:
        try: # blender 5
            channelbag = anim_utils.action_get_channelbag_for_slot(anim_data.action, anim_data.action_slot)
            fcurves = channelbag.fcurves
        except: pass

    BONES = {}
    if fcurves:
        numframes = 1+context.scene.frame_end-context.scene.frame_start
        for frame in range(numframes):
            fcurve_cache = {}
            for fcurve in fcurves:
                value = fcurve.evaluate(frame)
                path  = fcurve.data_path
                if path not in fcurve_cache: fcurve_cache[path] = []
                fcurve_cache[path].append(value)

            for pbone in arm_obj.pose.bones:
                loc_path   = f'pose.bones["{pbone.name}"].location'
                rot_q_path = f'pose.bones["{pbone.name}"].rotation_quaternion'
                scale_path = f'pose.bones["{pbone.name}"].scale'
                try:
                    loc = mathutils.Vector((v for v in fcurve_cache[loc_path]))
                    rot = mathutils.Quaternion((v for v in fcurve_cache[rot_q_path]))
                    scl = mathutils.Vector((v for v in fcurve_cache[scale_path]))            
                    mtx = mathutils.Matrix.LocRotScale(loc,rot,scl)
                except:
                    mtx = mathutils.Matrix.Identity(4)
                if pbone.name not in BONES: BONES[pbone.name] = []
                BONES[pbone.name].append(mtx)
    else: # dummy animation of two frames (rest pose)
        numframes = 2
        for frame in range(numframes):
            for pbone in arm_obj.pose.bones:
                if pbone.name not in BONES: BONES[pbone.name] = []
                BONES[pbone.name].append(mathutils.Matrix.Identity(4))

    out = bytearray(b'skel') # magic_bytes
    duration = numframes / context.scene.render.fps
    numbones = len(arm_obj.data.bones)
    out += struct.pack('<fI', duration, numbones)
    for pbone in arm_obj.pose.bones:
        out += strToBytes(pbone.name)
        out += struct.pack('<I', numframes)
        for frame in range(numframes):
            # timestamp
            out += struct.pack('<f', frame * duration / numframes)
            # key
            matrix_basis = BONES[pbone.name][frame]
            mtx = pbone.bone.matrix_local
            if pbone.parent: mtx = pbone.parent.bone.matrix_local.inverted() @ mtx
            mtx = mtx @ matrix_basis
            mtx = pkspc.inverted() @ mtx.transposed() @ pkspc.inverted().transposed()
            flat = [item for row in mtx for item in row]
            out += struct.pack('16f', *flat)
    file.write(out)