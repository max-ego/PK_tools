from bpy_extras.io_utils import (
    ImportHelper,
    ExportHelper,
    orientation_helper,
    axis_conversion,
)


from bpy.props import (
    BoolProperty,
    EnumProperty,
    StringProperty,
    IntProperty,
    FloatProperty,
)


import bpy
bl_info = {
    "name": "Painkiller MPK/DAT format",
    "author": "dilettante",
    "version": (3, 6, 0),
    "blender": (4, 2, 2),
    "location": "File > Import-Export",
    "description": "Painkiller WorldMesh Import/Export",
    "doc_url": "https://github.com/max-ego/PK_tools/",
    "category": "Import-Export",
}


if "bpy" in locals():
    import importlib
    if "common" in locals():
        importlib.reload(common)
    if "mpkexp" in locals():
        importlib.reload(mpkexp)
    if "datexp" in locals():
        importlib.reload(datexp)
    if "pk_import" in locals():
        importlib.reload(pk_import)
    if "pk_export" in locals():
        importlib.reload(pk_export)


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
        from . import pk_import

        keywords = self.as_keywords(ignore=("filter_glob",))

        return pk_import.load(self, context, **keywords)

    def draw(self, context):
        box = self.layout.box()
        box.prop( self, 'use_lightmaps' )
        box.prop( self, 'use_blendmaps' )
        box.prop( self, 'remove_doubles' )


def ensure_filepath_matches_export_format(filepath, export_format):
    import os
    filename = os.path.basename(filepath)
    if not filename: return filepath

    stem,ext = os.path.splitext(filename)
    if stem.startswith('.') and not ext: stem,ext = '',stem

    desired_ext = '.mpk' if export_format == 'MPK' else '.dat'
    ext_lower = ext.lower()
    if ext_lower not in ['.mpk', '.dat']:
        return filepath + desired_ext
    elif ext_lower != desired_ext:
        return filepath[:-len(ext)] + desired_ext
    else:
        return filepath


def on_export_format_changed(self, context):

    # Update the filename in the file browser when the format (.mpk/.dat) changes
    sfile = context.space_data
    if not isinstance(sfile, bpy.types.SpaceFileBrowser): return
    if not sfile.active_operator: return
    if sfile.active_operator.bl_idname != "EXPORT_SCENE_OT_pkmpk": return
    
    sfile.params.filename = ensure_filepath_matches_export_format(
        sfile.params.filename,
        self.export_format,
    )

    # change the filter
    sfile.params.filter_glob = '*.mpk' if self.export_format == 'MPK' else '*.dat'
    # update file list
    bpy.ops.file.refresh()


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
    """Export to MPK/DAT file format (.mpk/.dat)"""
    bl_idname = "export_scene.pkmpk"
    bl_label = 'Export MPK/DAT'
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ''
    filter_glob: StringProperty(default="*.mpk", options={'HIDDEN'})

    export_format: EnumProperty(
        name = 'Format',
        items = (('MPK', '(*.mpk)','Map'),('DAT','(*.dat)', 'Item | Map')),
        description = "Export format",
        default=0,
        update=on_export_format_changed,
    )

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

    scale_factor: FloatProperty(
        name="Scale Factor",
        description="Master scale factor for all objects",
        min=0.0, max=100000.0,
        soft_min=0.0, soft_max=100000.0,
        precision=3,
        default=1.0,
    )

    def check(self, _context):
        old_filepath = self.filepath
        self.filepath = ensure_filepath_matches_export_format(
            self.filepath,
            self.export_format,
        )
        return self.filepath != old_filepath

    def invoke(self, context, event):
        self.filter_glob = '*.mpk' if self.export_format == 'MPK' else '*.dat'
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        from . import pk_export

        keywords = self.as_keywords(ignore=("axis_forward",
                                            "axis_up",
                                            "filter_glob",
                                            "export_format",
                                            "check_existing",
                                            "dat_swt",
                                            "opt_swt",
                                            "sel_swt",
                                            ))

        global_matrix = axis_conversion(from_forward=self.axis_forward,
                                        from_up=self.axis_up,
                                        ).to_4x4()
        keywords["global_matrix"] = global_matrix

        return pk_export.load(self, context, **keywords)

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
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False
        self.layout.prop( self, 'scale_factor' )
        self.layout.prop( self, 'export_format' )


# Add to a menu
def menu_func_import(self, context):
    self.layout.operator(ImportMPK.bl_idname, text="Painkiller WorldMesh (.mpk/.dat)")


def menu_func_export(self, context):
    self.layout.operator(ExportMPK.bl_idname, text="Painkiller WorldMesh (.mpk/.dat)")


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
