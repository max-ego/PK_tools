from .common import *


def load_mpk(file):
    file.seek(-8, io.SEEK_END)
    numobj = read_long(file)

    addr = []
    temp = 0 - (8 + numobj * 4)
    file.seek(temp, io.SEEK_END)
    for i in range(numobj):
        addr.append(read_long(file))

    mtl_cache = {}
    image_cache = {}
    for i in range(numobj):
        geom = MeshIn('', 0, 0, [], 0, [], 0, [], '', 0x02, 0, 0, 0)
        CacheMeshMPK(file, addr[i], geom)
        BuildMesh(geom)


def CacheMeshMPK(file, addr, geom):
    file.seek(addr, io.SEEK_SET)
    magicBytes = read_long(file)
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
            if magicBytes == 0xDEAFBABE:
                file.seek(4, io.SEEK_CUR) # 0x0
                vert.u = read_float(file)
                vert.v = 1 - read_float(file)
                vert.u2 = read_float(file)
                vert.v2 = 1 - read_float(file)
            else: # 0xDEADBABE
                vert.u = read_float(file)
                vert.v = 1 - read_float(file)
                vert.u2 = read_float(file)
                vert.v2 = 1 - read_float(file)
                file.seek(24, io.SEEK_CUR) # tangents - ?
                vert.nx = read_float(file)
                vert.nz = read_float(file)
                vert.ny = -read_float(file)
        else:
            vert.nx = read_float(file)
            vert.nz = read_float(file)
            vert.ny = -read_float(file)
            vert.u = read_float(file)
            vert.v = 1 - read_float(file)
        geom.verts.append(vert)

    # normals if 2-ch
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

    if magicBytes != 0xDEAFBABE and geom.numchannels == 2: file.seek(4, io.SEEK_CUR) # - ?
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