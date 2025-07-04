from bpy_extras.io_utils import (
    ImportHelper,
    ExportHelper,
    orientation_helper,
    axis_conversion,
)


from bpy.props import (
    BoolProperty,
    StringProperty,
    IntProperty,
)


import bpy
bl_info = {
    "name": "Painkiller MPK format",
    "author": "dilettante",
    "version": (3, 5, 0),
    "blender": (4, 2, 2),
    "location": "File > Import-Export",
    "description": "Painkiller WorldMesh Import/Export",
    "doc_url": "https://github.com/max-ego/PK_tools/",
    "category": "Import-Export",
}


if "bpy" in locals():
    import importlib
    if "import_mpk" in locals():
        importlib.reload(import_mpk)
    if "export_mpk" in locals():
        importlib.reload(export_mpk)


class ImportMPK(bpy.types.Operator, ImportHelper):
    """Import from MPK/DAT file format (.mpk/.dat)"""
    bl_idname = "import_scene.pkmpk"
    bl_label = 'Import MPK/DAT'
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".mpk"
    filter_glob: StringProperty(default="*.mpk;*.dat", options={'HIDDEN'})

    use_lightmaps : BoolProperty(
            name = "Enable lightmaps",
            description = "Adds lightmaps to materials",
            default = True )

    use_blendmaps : BoolProperty(
            name = "Enable blendmaps",
            description = "Adds blendmaps to materials",
            default = True )

    remove_doubles : BoolProperty(
            name = "Merge vertices",
            description = "Removes double vertices",
            default = True )

    def execute(self, context):
        from . import import_mpk

        keywords = self.as_keywords(ignore=("filter_glob",))

        return import_mpk.load(self, context, **keywords)

    def draw(self, context):
        box = self.layout.box()
        box.prop( self, 'use_lightmaps' )
        box.prop( self, 'use_blendmaps' )
        box.prop( self, 'remove_doubles' )


def _optimization_switch(self, context):
    val = (self.use_default << 1 | self.use_optimize << 0)
    match (self.opt_swt ^ val):
        case 0b10: # default
            if (val & 0b10):
                if val & 0b01: self.use_optimize = False
                self.opt_swt = 0b10
            else: self.use_default = True
        case 0b01: # optimize
            if (val & 0b01):
                if val & 0b10: self.use_default = False
                self.opt_swt = 0b01
            else: self.use_optimize = True


def _selection_switch(self, context):
    val = (self.use_all << 2 | self.use_selection << 1 | self.use_visible << 0)
    match (self.sel_swt ^ val):
        case 0b100: # all
            if (val & 0b100):
                if val & 0b010: self.use_selection = False
                if val & 0b001: self.use_visible = False
                self.sel_swt = 0b100
            else: self.use_all = True
        case 0b010: # selection
            if (val & 0b010):
                if val & 0b100: self.use_all = False
                if val & 0b001: self.use_visible = False
                self.sel_swt = 0b010
            else: self.use_selection = True
        case 0b001: # visible
            if (val & 0b001):
                if val & 0b100: self.use_all = False
                if val & 0b010: self.use_selection = False
                self.sel_swt = 0b001
            else: self.use_visible = True


@orientation_helper(axis_forward='Y', axis_up='Z')
class ExportMPK(bpy.types.Operator, ExportHelper):
    """Export to MPK file format (.mpk)"""
    bl_idname = "export_scene.pkmpk"
    bl_label = 'Export MPK'
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".mpk"
    filter_glob: StringProperty(default="*.mpk", options={'HIDDEN'})
            
    opt_swt : IntProperty( default = 0b10 )

    use_default : BoolProperty(
            name = "Default",
            description = "Standard conversion",
            default = True,
            update = _optimization_switch )

    use_optimize : BoolProperty(
            name = "Optimize",
            description = "Remove double vertices",
            default = False,
            update = _optimization_switch )
            
    sel_swt : IntProperty( default = 0b100 )

    use_all: BoolProperty(
            name="All",
            description="Export all objects",
            default = True,
            update = _selection_switch )

    use_selection: BoolProperty(
            name="Selection",
            description="Export selected objects only",
            default = False,
            update = _selection_switch )

    use_visible: BoolProperty(
            name="Visible",
            description="Export visible objects only",
            default = False,
            update = _selection_switch )

    use_sort: BoolProperty(
            name="Sort",
            description="Sort faces by materials",
            default = False )

    def execute(self, context):
        from . import export_mpk

        keywords = self.as_keywords(ignore=("axis_forward",
                                            "axis_up",
                                            "filter_glob",
                                            "check_existing",
                                            "opt_swt",
                                            "sel_swt",
                                            ))

        global_matrix = axis_conversion(from_forward=self.axis_forward,
                                        from_up=self.axis_up,
                                        ).to_4x4()
        keywords["global_matrix"] = global_matrix

        return export_mpk.load(self, context, **keywords)

    def draw(self, context):
        box1 = self.layout.box()
        box1.prop( self, 'use_default' )
        box1.prop( self, 'use_optimize' )
        box2 = self.layout.box()
        box2.prop( self, 'use_all' )
        box2.prop( self, 'use_selection' )
        box2.prop( self, 'use_visible' )        
        box3 = self.layout.box()
        box3.prop( self, 'use_sort' )


# Add to a menu
def menu_func_import(self, context):
    self.layout.operator(ImportMPK.bl_idname, text="Painkiller WorldMesh (.mpk/.dat)")


def menu_func_export(self, context):
    self.layout.operator(ExportMPK.bl_idname, text="Painkiller WorldMesh (.mpk)")


def register():
    bpy.utils.register_class(ImportMPK)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.utils.register_class(ExportMPK)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ImportMPK)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(ExportMPK)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()
