from bpy_extras.io_utils import (
    ImportHelper,
)
from bpy.props import (
    BoolProperty,
    StringProperty,
)

import bpy
bl_info = {
    "name": "Painkiller MPK format",
    "author": "dilettante",
    "version": (2, 0, 0),
    "blender": (4, 2, 2),
    "location": "File > Import-Export",
    "description": "Painkiller WorldMesh Import",
    "doc_url": "https://github.com/max-ego/PK_tools/",
    "category": "Import-Export",
}

if "bpy" in locals():
    import importlib
    if "import_mpk" in locals():
        importlib.reload(import_mpk)

class ImportMPK(bpy.types.Operator, ImportHelper):
    """Import from MPK file format (.mpk)"""
    bl_idname = "import_scene.pkmpk"
    bl_label = 'Import MPK'
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".mpk"
    filter_glob: StringProperty(default="*.mpk", options={'HIDDEN'})

    use_lightmaps : BoolProperty(
            name = "Enable lightmaps",
            description = "Adds lightmaps to materials",
            default = True )

    def execute(self, context):
        from . import import_mpk

        keywords = self.as_keywords(ignore=("filter_glob",))

        return import_mpk.load(self, context, **keywords)

    def draw(self, context):
        self.layout.box().prop( self, 'use_lightmaps' )

# Add to a menu
def menu_func_import(self, context):
    self.layout.operator(ImportMPK.bl_idname, text="Painkiller WorldMesh (.mpk)")


def register():
    bpy.utils.register_class(ImportMPK)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(ImportMPK)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
