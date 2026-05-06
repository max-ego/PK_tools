from .common import *


@dataclass
class Skin:
    skinname : str
    skel     : []
    geometry : []
    type     : int # - ?
    index    : int
    size     : int
    offset   : int


def CachePKMDL(file):
    file.seek(0, io.SEEK_SET)
    namelist = []
    for i in range(read_long(file)): namelist.append(readString(file))
    model = []
    skincount = read_long(file)
    for i in range(skincount):
        model.append(Skin('',[],[],0,0,0,0))
        temp = read_long(file) # 0x0
        model[i].type = read_long(file)
        index = read_long(file)
        model[i].index = index
        model[i].skinname = namelist[index]
        model[i].size = read_long(file)
        model[i].offset = read_long(file)

    for i in range(skincount):
        file.seek(model[i].offset, io.SEEK_SET)
        if model[i].index == 0:
            model[i].skinname = readString(file)
            model[i].type = 1 << model[i].type
        else:
            readString(file)
        model[i].skinname = os.path.basename(model[i].skinname).split('.', 1)[0]
        # skeleton
        numskels = read_short(file)
        numbones = read_long(file)
        currparent = -1
        for ii in range(numbones):
            bonename = readString(file)
            data = struct.unpack('<16f', file.read(64))
            mtx=mathutils.Matrix((data[0:4],data[4:8],data[8:12],data[12:16]))
            try: model[i].skel[currparent].numchildren-=1
            except: pass
            numchildren = file.read(1)[0]
            model[i].skel.append(
                SimpleNamespace(name=bonename,tm=mtx,numchildren=numchildren,parent=currparent)
                )
            currparent=ii
            if model[i].skel[ii].numchildren==0:
                while currparent>=0 and model[i].skel[currparent].numchildren==0: currparent-=1
        # mesh objects
        for ii in range(read_long(file)):
            geom = MeshIn('', 1, 0, [], 0, [], 0, [], 0x02, 0, 0, 0)
            geom.meshname = readString(file)
            # materials
            readString(file) # 0x0
            readString(file) # 0x0
            geom.normalmap = readString(file)
            nummat = read_long(file)
            geom.nummat = nummat
            for iii in range(nummat):
                colormap = os.path.basename(readString(file)).split('.', 1)[0]
                lightmap = ''
                offset   = read_long(file)
                size     = read_long(file)
                mat = Material(offset, size,
                    colormap, UV(0, 0), UV(1, 1),
                    lightmap, UV(0, 0), UV(1, 1),
                    '', UV(0, 0), UV(1, 1),
                    '', UV(0, 0), UV(1, 1),
                )
                geom.mat.append(mat)
            # faces
            geom.numFaces = int(read_long(file)/3)
            for iii in range(geom.numFaces):
                v0,v1,v2 = read_short(file), read_short(file), read_short(file)
                geom.faces.append(Face(v0,v1,v2))
            read_long(file)  # 0x0
            # vertices
            geom.numVerts = read_long(file)
            for iii in range(geom.numVerts):
                data = file.read(32)
                x,z,y,nx,nz,ny,u,v = struct.unpack('<8f', data)
                geom.verts.append(Vertex(x,-y,z,nx,-ny,nz,u,1-v,0,0))
            read_long(file) # 0x0
            read_long(file) # 0x0
            # skinning
            geom.weights = []
            numVerts = read_long(file)
            for iii in range(numVerts):
                influences = []
                for iiii in range(read_long(file)):
                    influences.append(
                        SimpleNamespace(bone_idx=read_short(file),weight=read_float(file))
                    )
                geom.weights.append(influences)
            model[i].geometry.append(geom)
    return model


def BuildSkeleton(skin):
    armature = bpy.data.armatures.new(skin.skinname+'_Armature')
    armature.display_type = 'ENVELOPE' # 'OCTAHEDRAL' 'STICK' 'BBONE' 'ENVELOPE' 'WIRE'
    arm_obj = bpy.data.objects.new('Armature', armature)
    bpy.context.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')

    bones = []
    names = []
    for bone in skin.skel:
        edit_bone = armature.edit_bones.new(bone.name)
        edit_bone.head = (0,0,0) # select armature  >  Tab(edit mode)  >  A
        edit_bone.tail = (0,1,0) # Alt+S OR Ctrl+Alt+Shift+S AND mouse move
        mtx = bone.tm
        if bone.parent != -1:
            edit_bone.parent = bones[bone.parent]
            parent = bone.parent
            while parent != -1:
                mtx = mtx @ skin.skel[parent].tm
                parent = skin.skel[parent].parent
        mtx = pkspc @ mtx.transposed() @ pkspc.transposed()
        edit_bone.matrix = mtx
        bones.append(edit_bone)
        names.append(edit_bone.name)

    bpy.ops.object.mode_set(mode='OBJECT')
    return arm_obj, names


def SetWeights(arm_obj, names, mesh_obj, weights):    
    mod = mesh_obj.modifiers.new(name='Weights', type='ARMATURE')
    mod.object = arm_obj
    vertex_groups = {}
    for v,influences in enumerate(weights):
        for influence in influences:
            bone_name = names[influence.bone_idx]
            if bone_name not in mesh_obj.vertex_groups:
                vertex_groups[bone_name] = mesh_obj.vertex_groups.new(name=bone_name)
            vertex_groups[bone_name].add([v], influence.weight, 'ADD')


def load_mdl(file):
    pkmdl = CachePKMDL(file)
    mtl_cache = {}
    image_cache = {}
    for skin in pkmdl:
        arm_obj, names = BuildSkeleton(skin)
        for geom in skin.geometry:
            mesh_obj = BuildMesh(geom)
            SetWeights(arm_obj, names, mesh_obj, geom.weights)
        # PKMDL is a collection of skinned rigs
        # we only run against the first element
        break


def CacheAnim(file):
    read_long(file) # magic_bytes 'skel'
    duration = read_float(file) # in seconds
    numbones = read_long(file)
    anim = SimpleNamespace(duration=duration,numbones=numbones,bones=[])
    for i in range(numbones):
        name = file.read(read_long(file)).decode('iso-8859-1')
        bone = SimpleNamespace(name=name,numframes=read_long(file),keys=[])
        for i in range(bone.numframes):
            timestamp = read_float(file)
            data = struct.unpack('<16f', file.read(64))
            m=mathutils.Matrix((data[0:4],data[4:8],data[8:12],data[12:16]))
            bone.keys.append(SimpleNamespace(timestamp=timestamp,tm=m))
        anim.bones.append(bone)
    return anim


def load_ani(file, context, bUseScale = False, bCloseLoop = False):
    anim = CacheAnim(file)

    try: arm_obj=[obj for obj in context.scene.objects if obj.type == 'ARMATURE'][0]
    except: return

    action_name = os.path.splitext(os.path.basename(file.name))[0]
    action = bpy.data.actions.new(name=action_name)
    if not arm_obj.animation_data:
        arm_obj.animation_data_create()
    arm_obj.animation_data.action = action

    numframes = anim.bones[0].numframes + int(bCloseLoop)
    context.scene.frame_end = numframes
    context.scene.render.fps_base = 1
    context.scene.render.fps = int(round(numframes/anim.duration))

    BONES = {}
    for bone in anim.bones:
        try: pose_bone = arm_obj.pose.bones[bone.name]
        except: continue
        BONES[pose_bone.name]=[]
        if bCloseLoop: bone.keys.append(bone.keys[0])
        for i,key in enumerate(bone.keys):
            mtx = key.tm
            if not bUseScale:
                # parent to world
                pbone = arm_obj.pose.bones[bone.name]
                while pbone.parent:
                    for _bone in anim.bones:
                        if pbone.parent and _bone.name == pbone.parent.name:
                            mtx = mtx @ _bone.keys[i].tm
                            pbone = arm_obj.pose.bones[_bone.name]
                # pk to blender
                mtx = pkspc @ mtx.transposed() @ pkspc.transposed()
                # !!! REMOVE SCALING !!!
                loc,rot,scl = mtx.decompose()
                mtx = mathutils.Matrix.LocRotScale(loc,rot,None)
                # store absolute transform
                BONES[pose_bone.name].append(mtx)
                # world to parent
                if pose_bone.parent:
                    mtx = BONES[pose_bone.parent.name][i].inverted() @ mtx
            else:
                mtx = pkspc @ mtx.transposed() @ pkspc.transposed()
            # parent to rest ('matrix_basis' is identity in a rest pose)
            if pose_bone.parent:
                matrix_basis = pose_bone.bone.matrix_local.inverted() @ \
                pose_bone.parent.bone.matrix_local @ mtx
            else:
                matrix_basis = pose_bone.bone.matrix_local.inverted() @ mtx
            # apply transform
            pose_bone.matrix_basis = matrix_basis
            pose_bone.keyframe_insert(data_path='location',           frame=i)
            pose_bone.keyframe_insert(data_path='rotation_quaternion',frame=i)
            pose_bone.keyframe_insert(data_path='scale',              frame=i)