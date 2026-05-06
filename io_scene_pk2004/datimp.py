from .common import *


def load_dat(file):
    geometry = CacheMeshDAT(file)
    mtl_cache = {}
    image_cache = {}    
    for geom in geometry: BuildMesh(geom)


def CacheMeshDAT(file):
    file.seek(0, io.SEEK_SET)
    namelist = []
    for i in range(read_long(file)):
        namelist.append(readString(file))

    numobj = read_long(file)
    geometry = []
    for i in range(numobj):
        geometry.append(MeshIn('', 0, 0, [], 0, [], 0, [], 0x02, 0, 0, 0))
        temp = read_long(file) # 0x0
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
            """
            ---------------------------
            |       type | item | map |
            ---------------------------
            | renderable | 0x02 |  1  |
            |       zone | 0x04 |  2  |
            |     portal | 0x08 |  3  |
            |      antyp | 0x10 |  4  |
            ---------------------------
            """
            geometry[i].type = 1 << geometry[i].type
        else:
            readString(file)

        if geometry[i].type == 0x02:
            geometry[i].numchannels = 1 if read_long(file) & 0x0400 else 2

        # ANTYP : never appears in any original file
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

            geometry[i].numVerts = read_long(file)

            geometry[i].numFaces = 2
            if geometry[i].numVerts == 4:
                geometry[i].faces.append(Face(2, 1, 0))
                geometry[i].faces.append(Face(0, 3, 2))
            else:
                geometry[i].faces.append(Face(0, 1, 2))
                geometry[i].faces.append(Face(3, 4, 5))
            
            for ii in range(geometry[i].numVerts):
                pt = pkspc @ mathutils.Vector((read_float(file),read_float(file),read_float(file)))
                vert = Vertex(pt.x, pt.y, pt.z, 0,0,0,0,0,0,0)
                geometry[i].verts.append(vert)
            continue

        # matrix
        file.seek(64, io.SEEK_CUR)

        # 0x0 - ?
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
            file.seek(SZ_SHORT*num_verts, io.SEEK_CUR)

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

        # vertices
        geometry[i].numVerts = read_long(file)
        for ii in range(geometry[i].numVerts):
            vert = Vertex(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            vert.x = read_float(file)
            vert.z = read_float(file)
            vert.y = -read_float(file)

            if geometry[i].numchannels == 2:
                file.seek(4, io.SEEK_CUR) # 0x0
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
        # normals if 2-ch
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
        file.seek(read_long(file)*8*SZ_FLOAT, io.SEEK_CUR)

    return geometry