from .common import *


from .mpkexp import save_mpk
from .datexp import save_dat
from .mdlexp import save_mdl
from .mdlexp import save_ani


def load(operator, context, filepath='', use_default=True, use_optimize=False, use_all=True, use_selection=False, use_visible=False, use_sort=False, scale_factor=1.0, global_matrix=None):
    
    global filetype; filetype = Path(filepath).suffix.split('.')[-1].upper()

    # global bDefault;   bDefault   = use_default
    global bOptimize;  bOptimize  = use_optimize
    global bAll;       bAll       = use_all
    global bSelection; bSelection = use_selection
    global bVisible;   bVisible   = use_visible
    global bSort;      bSort      = use_sort
    global scale;      scale      = scale_factor

    save_data(filepath, context, global_matrix)

    return {'FINISHED'}


def save_data(filepath, context, global_matrix):

    try: file = open(filepath, 'wb')
    except:
        info('access denied : \'' + filepath + '\'', icon='ERROR')
        return

    print(f'exporting {filetype}: %r...' % filepath)

    duration = time.time()
    context.window.cursor_set('WAIT')

    # try:
    params = (filetype, bOptimize, bAll, bSelection, bVisible, bSort, scale)
    match filetype:
        case 'MPK'  : save_mpk(file, context, global_matrix, params)
        case 'DAT'  : save_dat(file, context, global_matrix, params)
        case 'PKMDL': save_mdl(file, context, global_matrix, params)
        case 'ANI'  : save_ani(file, context)
    info('success', icon='INFO')
    # except:
        # info('something went wrong', icon='ERROR')

    file.close()

    context.window.cursor_set('DEFAULT')
    print(f'{filetype} export time: %.2f' % (time.time() - duration))
