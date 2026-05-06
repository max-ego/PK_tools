from .common import *


from .mpkimp import load_mpk
from .datimp import load_dat
from .mdlimp import load_mdl
from .mdlimp import load_ani


def load(operator, context, filepath='', use_lightmaps=True, use_blendmaps=True, remove_doubles=True, use_scale=False, close_seq=False):

    global filetype; filetype = Path(filepath).suffix.split('.')[-1].upper()

    global info

    def info(msg='', icon='INFO'): operator.report({icon}, f'{filetype} Import : {msg}')

    load_data(filepath, context, use_lightmaps, use_blendmaps, remove_doubles, use_scale, close_seq)

    return {'FINISHED'}


def load_data(filepath, context, use_lightmaps, use_blendmaps, remove_doubles, use_scale, close_seq):

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

    dirname = os.path.dirname(file.name)
    set_glob(params=(tm,bLightmaps,bBlendmaps,dirname))

    print(f'importing {filetype}: \'{filepath}\'...')

    duration = time.time()
    context.window.cursor_set('WAIT')
    
    # try:
    match filetype:
        case 'MPK'  : load_mpk(file)
        case 'DAT'  : load_dat(file)
        case 'PKMDL': load_mdl(file)
        case 'ANI'  : load_ani(file, context, use_scale, close_seq)
    try:
        for ob in bpy.data.collections['___zone___'].all_objects:
            ob.select_set(True)
        bpy.ops.object.shade_flat()
        bpy.ops.object.select_all(action='DESELECT')
    except: pass        
    if bRemoveDoubles: RemoveDoubles()
    
    info('success', icon='INFO')
    # except:
        # info('something went wrong', icon='ERROR')

    file.close()

    try:
        view_3d = [area for area in bpy.context.window.screen.areas if area.type == 'VIEW_3D'][0]
        with bpy.context.temp_override(area=view_3d):
            bpy.context.space_data.shading.show_backface_culling = True
    except: pass

    context.window.cursor_set('DEFAULT')
    print(f'{filetype} import time: %.2f' % (time.time() - duration))
