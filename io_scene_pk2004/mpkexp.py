from .common import *


def dumpMPK(file, ob):
    # magic bytes
    write_long(file,0xDEAFBABE)

    # mesh name
    write_long(file,len(ob.name)+1)
    writeString(file,ob.name)

    # transform matrix
    dummy = struct.pack('<16f', 1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1)
    file.write(dummy)

    # vertices
    write_long(file,ob.numUVs)
    write_long(file,len(ob.verts))
    for key in ob.verts:
        file.write(key[0:12])
        if ob.numUVs == 2:
            write_float(file,0)
            file.write(key[24:40])
        else:
            file.write(key[12:32])
    # normals if 2-ch
    if ob.numUVs == 2:
        write_long(file,len(ob.verts))
        for key in ob.verts:
            file.write(key[12:24])
    else:
        write_long(file,0)

    # bounding box
    file.write(ob.bbox)

    # faces
    write_long(file,len(ob.faces)*3)
    for f in ob.faces:
        write_short(file,f[0])
        write_short(file,f[2])
        write_short(file,f[1])

    # materials
    mtl_offset = 0
    num_mtls = len(ob.mtls)
    write_long(file,num_mtls)
    for i in range(num_mtls):
        write_short(file,mtl_offset)
        mtl_len = ob.mtls.get(i)[0]
        mtl_idx = ob.mtls.get(i)[1]
        mtl = ob.materials[mtl_idx]
        mtl_offset += mtl_len * 3
        write_short(file,mtl_len)
        # color map : uses 1st UV-channel
        texName = mtl.get('color')
        write_long(file,len(texName)+1)
        writeString(file,texName)
        mapping = struct.pack('<4f', mtl.get('c_loc')[0], mtl.get('c_loc')[1], mtl.get('c_scl')[0], mtl.get('c_scl')[1])
        file.write(mapping)
        # light map : uses 2nd UV-channel
        texName = mtl.get('light')
        if texName is None: texName = fname(ob.lm)
        write_long(file,len(texName)+1)
        writeString(file,texName)
        mapping = struct.pack('<4f', 0, 0, 1, 1)
        file.write(mapping)
        # blend map : uses 1st UV-channel
        texName = mtl.get('blend')
        write_long(file,len(texName)+1)
        writeString(file,texName)
        mapping = struct.pack('<4f', mtl.get('b_loc')[0], mtl.get('b_loc')[1], mtl.get('b_scl')[0], mtl.get('b_scl')[1])
        file.write(mapping)
        # alpha map : uses 2nd UV-channel
        texName = mtl.get('alpha')
        write_long(file,len(texName)+1)
        writeString(file,texName)
        mapping = struct.pack('<4f', 0, 0, 1, 1)
        file.write(mapping)


def save_mpk(file, context, global_matrix, params):
    data = getGeometry(file, context, global_matrix, params)
    offsets = []
    for ob in data.geom:
        offsets.append(file.tell())
        dumpMPK(file, ob)
    for offset in offsets:
        write_long(file, offset)
    write_long(file, len(offsets))
    write_long(file, 0xDEADBEEF) # trailer