from .common import *


def getDATsize(ob):
    size = SZ_INT + len(ob.name)+1                      # name
    if ob.type == 0x10:
        size += SZ_INT                                  # vertcount
        size += len(ob.verts)*3*SZ_FLOAT                # vertices
        size += SZ_INT                                  # facecount
        size += len(ob.faces)*3*SZ_SHORT                # faces
        return size                                     # Antyp    
    if ob.type == 0x02: size += SZ_INT                  # flags
    size += SZ_FLOAT *  6                               # bbox
    if ob.type == 0x04: return size                     # Zone
    if ob.type == 0x08:
        size += SZ_INT                                  # vertcount
        size += len(ob.verts)*3*SZ_FLOAT                # vertices
        return size                                     # Portal
    size += SZ_FLOAT * 16                               # matrix
    size += SZ_INT                                      # 0x0
    mtl_idx = ob.mtls.get(0)[1]
    mtl = ob.materials[mtl_idx]
    texName = mtl.get('light')
    if texName is None: texName = fname(ob.lm)
    size += SZ_INT                                      # name len
    size += (1,len(texName)+1)[ob.numUVs==2]            # texname
    size += (SZ_INT + len('notex')+1)                   # 'notex'
    size += SZ_INT                                      # mtlcount
    for i in range(len(ob.mtls)):
        mtl_idx = ob.mtls.get(i)[1]
        mtl = ob.materials[mtl_idx]
        size += (SZ_INT + len(mtl.get('color'))+1)      # color
        size += SZ_INT                                  # offset
        size += SZ_INT                                  # size
    size += SZ_INT                                      # facecount
    size += len(ob.faces)*3*SZ_SHORT                    # faces
    size += SZ_INT                                      # 0x0
    size += SZ_INT                                      # vertcount
    size += len(ob.verts)*8*SZ_FLOAT                    # vertices
    size += SZ_INT                                      # normalcount
    size += (0,len(ob.verts)*3*SZ_FLOAT)[ob.numUVs==2]  # normals
    size += SZ_INT                                      # tangentcount
    return size


def dumpDAT(file, data):
    # header
    numobj = len(data.geom)
    datfilename = os.path.basename(file.name)
    if data.bIsItem:
        data.geom.insert(0, MeshOut(datfilename,[],1,[],[],{},[],'',0x0))
        data.geom.insert(2, MeshOut('WorldMesh',[],1,[],[],{},[],'',0x0))
        names = [ob.name for ob in data.geom]
    else:
        names = [datfilename,'WorldMesh','Zone','Portal','AntiPortal']
    write_long(file,len(names))
    for name in names:
        write_long(file,len(name)+1)
        writeString(file,name)
    write_long(file,numobj)
    offset = file.tell() + numobj*5*SZ_INT
    index = 0    
    for ob in data.geom:
        if ob.type == 0x0:
            index += 1
            continue
        write_long(file,0) # 0x0
        """
        ---------------------------
        | map | item | type       |
        ---------------------------
        |  1  | 0x02 | renderable |
        |  2  | 0x04 | zone       |
        |  3  | 0x08 | portal     |
        |  4  | 0x10 | antyp      |
        ---------------------------
        """
        type = ((ob.type).bit_length()-1,ob.type)[data.bIsItem]
        write_long(file,type)
        write_long(file,(0,index)[data.bIsItem])
        index += 1
        size = getDATsize(ob)
        write_long(file,size)
        write_long(file,offset)
        offset += size

    # body
    for ob in data.geom:
        if ob.type == 0x0: continue
        # name
        write_long(file,len(ob.name)+1)
        writeString(file,ob.name)

        # ANTYP
        if ob.type == 0x10:
            # verts
            write_long(file,len(ob.verts))
            for key in ob.verts:
                file.write(key[0:12])
            # faces
            write_long(file,len(ob.faces)*3)
            for f in ob.faces:
                write_short(file,f[0])
                write_short(file,f[2])
                write_short(file,f[1])
            continue
        
        # flags
        if ob.type == 0x02:
            bits = (0x0400,0)[ob.numUVs==2]
            if re.search(r'barrier', ob.name, re.IGNORECASE): bits = bits | 0x0040        
            write_long(file,bits)

        # bounding box
        file.write(ob.bbox)

        # ZONE
        if ob.type == 0x04: continue
        # PORTAL
        if ob.type == 0x08:
            write_long(file,len(ob.verts))
            for key in ob.verts:
                file.write(key[0:12])
            continue

        # transform matrix
        dummy = struct.pack('<16f', 1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1)
        file.write(dummy)

        # 0x0 - ?
        write_long(file,0)

        # materials
        mtl_idx = ob.mtls.get(0)[1]
        mtl = ob.materials[mtl_idx]
        # light map : 2nd UV-channel
        texName = mtl.get('light')
        if texName is None: texName = fname(ob.lm)
        write_long(file,len(texName)+1)
        writeString(file,texName)
        texName = 'notex'
        write_long(file,len(texName)+1)
        writeString(file,texName)
        # colorMaps
        mtl_offset = 0
        num_mtls = len(ob.mtls)
        write_long(file,num_mtls)
        for i in range(num_mtls):
            mtl_len = ob.mtls.get(i)[0]
            mtl_idx = ob.mtls.get(i)[1]
            mtl = ob.materials[mtl_idx]
            # color map : 1st UV-channel
            texName = mtl.get('color')
            write_long(file,len(texName)+1)
            writeString(file,texName)   # color
            write_long(file,mtl_offset) # offset
            write_long(file,mtl_len)    # size
            mtl_offset += mtl_len * 3

        # faces
        write_long(file,len(ob.faces)*3)
        for f in ob.faces:
            write_short(file,f[0])
            write_short(file,f[2])
            write_short(file,f[1])
        write_long(file,0)        
        # verts
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
            write_long(file,len(ob.verts)) # normals
            for key in ob.verts:
                file.write(key[12:24])
        else:
            write_long(file,0) # normals        
        # tangents
        write_long(file,0)


def saveDAT(file, context, global_matrix, params):
    data = getGeometry(file, context, global_matrix, params)
    dumpDAT(file, data)
