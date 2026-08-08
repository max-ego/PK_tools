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
    "name": "Painkiller (MPK/DAT/PKMDL/ANI) format",
    "author": "dilettante",
    "version": (4, 1, 1),
    "blender": (4, 2, 2),
    "location": "File > Import-Export",
    "description": "Painkiller Asset Import/Export",
    "doc_url": "https://github.com/max-ego/PK_tools/",
    "category": "Import-Export",
}


if "bpy" in locals():
    import importlib
    if "common" in locals():
        importlib.reload(common)
    if "mdlimp" in locals():
        importlib.reload(mdlimp)
    if "mdlexp" in locals():
        importlib.reload(mdlexp)
    if "mpkimp" in locals():
        importlib.reload(mpkimp)
    if "datimp" in locals():
        importlib.reload(datimp)
    if "mpkexp" in locals():
        importlib.reload(mpkexp)
    if "datexp" in locals():
        importlib.reload(datexp)
    if "pk_import" in locals():
        importlib.reload(pk_import)
    if "pk_export" in locals():
        importlib.reload(pk_export)


def on_use_hierarchy(self, context):
    if self.use_hierarchy:
        self.use_lightmaps = True
        self.use_blendmaps = True


def on_use_lightmaps(self, context):
    if not self.use_lightmaps: self.use_hierarchy = False


def on_use_blendmaps(self, context):
    if not self.use_blendmaps: self.use_hierarchy = False


class ImportMPK(bpy.types.Operator, ImportHelper):
    """Import from MPK/DAT file format (.mpk/.dat)"""
    bl_idname = "import_scene.pkmpk"
    bl_label = 'Import MPK/DAT'
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".mpk"
    filter_glob: StringProperty(default="*.mpk;*.dat", options={'HIDDEN'})

    use_lightmaps : BoolProperty(
            name = "Enable lightmaps",
            description = "Add lightmaps to materials",
            default = True,
            update = on_use_lightmaps )

    use_blendmaps : BoolProperty(
            name = "Enable blendmaps",
            description = "Add blendmaps to materials",
            default = True,
            update = on_use_blendmaps )

    remove_doubles : BoolProperty(
            name = "Merge vertices",
            description = "Remove double vertices",
            default = True )

    use_hierarchy : BoolProperty(
            name = "Directory hierarchy",
            description = "Respect directory hierarchy in texture search",
            default = False,
            update = on_use_hierarchy )

    def execute(self, context):
        from . import pk_import

        keywords = self.as_keywords(ignore=("filter_glob",))

        return pk_import.load(self, context, **keywords)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        import_panel_geometry(layout, self)
        import_panel_textures(layout, self)


def import_panel_geometry(layout, operator):
    header, body = layout.panel("PKMPK_import_geometry", default_closed=False)
    header.label(text="Geometry")
    if body:
        body.prop(operator, "use_lightmaps")
        body.prop(operator, "use_blendmaps")
        body.prop(operator, "remove_doubles")


def import_panel_textures(layout, operator):
    header, body = layout.panel("PKMPK_import_textures", default_closed=False)
    header.label(text="Textures")
    if body: body.prop(operator, "use_hierarchy")


def ensure_filepath_matches_format(filepath, fileformat):
    import os
    filename = os.path.basename(filepath)
    if not filename: return filepath

    stem,ext = os.path.splitext(filename)
    if stem.startswith('.') and not ext: stem,ext = '',stem

    desired_ext = '.' + fileformat.lower()
    ext_lower = ext.lower()
    if ext_lower not in ['.mpk', '.dat', '.pkmdl', '.ani']:
        return filepath + desired_ext
    elif ext_lower != desired_ext:
        return filepath[:-len(ext)] + desired_ext
    else:
        return filepath


def on_format_changed(self, context):

    # Update the filename in the file browser
    sfile = context.space_data
    if not isinstance(sfile, bpy.types.SpaceFileBrowser): return
    if not sfile.active_operator: return

    sfile.params.filename = ensure_filepath_matches_format(
        sfile.params.filename,
        self.fileformat,
    )

    # change the filter
    sfile.params.filter_glob = '*.' + self.fileformat.lower()
    
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
    filter_glob: StringProperty(default='*.mpk', options={'HIDDEN'})

    fileformat: EnumProperty(
        name = 'Format',
        items = (('MPK', '(*.mpk)','Map'),('DAT','(*.dat)', 'Item | Map')),
        description = "Export format",
        default = 0,
        update = on_format_changed )

    opt_swt : IntProperty( default = 0b10 )

    use_default : BoolProperty(
            name = "Off",
            description = "Standard conversion",
            default = True,
            update = _optimization_switch )

    use_optimize : BoolProperty(
            name = "On",
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
            default = True )

    use_path: BoolProperty(
            name="Preserve texture path",
            description="Preserve relative paths for textures",
            default = False )

    scale_factor: FloatProperty(
        name="Scale Factor",
        description="Master scale factor for all objects",
        min=0.0, max=100000.0,
        soft_min=0.0, soft_max=100000.0,
        precision=3,
        default=1.0,
    )

    def info(self, msg='', icon=''):
        self.report({icon}, f'{self.fileformat} Export : ' + msg)

    def check(self, _context):
        old_filepath = self.filepath
        self.filepath = ensure_filepath_matches_format(
            self.filepath,
            self.fileformat,
        )
        return self.filepath != old_filepath

    def invoke(self, context, event):
        self.filter_glob = '*.mpk' if self.fileformat == 'MPK' else '*.dat'
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        from . import pk_export

        keywords = self.as_keywords(ignore=("axis_forward",
                                            "axis_up",
                                            "filter_glob",
                                            "fileformat",
                                            "check_existing",
                                            "opt_swt",
                                            "sel_swt",
                                            "use_path",
                                            ))

        global_matrix = axis_conversion(from_forward=self.axis_forward,
                                        from_up=self.axis_up,
                                        ).to_4x4()
        keywords["global_matrix"] = global_matrix

        common.path = self.use_path
        common.info = self.info
        pk_export.info = self.info
        return pk_export.load(self, context, **keywords)

    def draw(self, context):        
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        self.layout.prop( self, 'fileformat' )

        export_panel_include(layout, self)
        export_panel_optimize(layout, self)
        export_panel_materials(layout, self)
        export_panel_transform(layout, self)


def export_panel_include(layout, operator):
    header, body = layout.panel("PKMPK_export_include", default_closed=False)
    header.label(text="Include")
    if body:
        body.prop(operator, "use_all")
        col = body.column(heading="Limit to")
        col.prop(operator, "use_selection")
        col.prop(operator, "use_visible")


def export_panel_optimize(layout, operator):
    header, body = layout.panel("PKMPK_export_optimize", default_closed=False)
    header.label(text="Optimize")
    if body:
        body.prop(operator, "use_default")
        body.prop(operator, "use_optimize")


def export_panel_materials(layout, operator):
    header, body = layout.panel("PKMPK_export_materials", default_closed=True)
    header.label(text="Material")
    if body:
        col = body.column(heading="Indices")
        col.prop(operator, "use_sort")
        col = body.column(heading="Textures")
        col.prop(operator, "use_path")


def export_panel_transform(layout, operator):
    header, body = layout.panel("PKMPK_export_transform", default_closed=True)
    header.label(text="Transform")
    if body: body.prop(operator, "scale_factor")


class ImportMDL(bpy.types.Operator, ImportHelper):
    """Import from PKMDL/ANI file format (.pkmdl/.ani)"""
    bl_idname = "import_scene.pkmdl"
    bl_label = 'Import PKMDL/ANI'
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ''
    filter_glob: StringProperty(default='*.pkmdl', options={'HIDDEN'})

    fileformat: EnumProperty(
        name = 'Format',
        items = (('PKMDL', '(*.pkmdl)','Model'),('ANI','(*.ani)', 'Animation')),
        description = "Import format",
        default = 0,
        update = on_format_changed )

    use_lightmaps : BoolProperty( default = False )
    use_blendmaps : BoolProperty( default = False )
    remove_doubles : BoolProperty( default = False )

    use_hierarchy : BoolProperty(
            name = "Directory hierarchy",
            description = "Respect directory hierarchy in texture search",
            default = False )

    use_scale: BoolProperty(
            name="Use scale",
            description="Consider scaling",
            default = False )

    close_seq: BoolProperty(
            name="Close loop",
            description="Add extra key",
            default = False )

    def invoke(self, context, event):
        self.filter_glob = '*.pkmdl' if self.fileformat == 'PKMDL' else '*.ani'
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from . import pk_import

        keywords = self.as_keywords(ignore=("filter_glob",
                                            "fileformat",
                                            ))

        return pk_import.load(self, context, **keywords)

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False
        self.layout.prop( self, 'fileformat' )
        header, body = self.layout.panel("MDL_ANI_import", default_closed=False)
        if self.fileformat == 'ANI':
            header.label( text="Animation" )
            if body:
                body.prop( self, "close_seq" )
                body.prop( self, "use_scale" )
        else:
            header.label( text="Textures" )
            if body:
                body.prop( self, "use_hierarchy" )


@orientation_helper(axis_forward='Y', axis_up='Z')
class ExportMDL(bpy.types.Operator, ExportHelper):
    """Export to PKMDL/ANI file format (.pkmdl/.ani)"""
    bl_idname = "export_scene.pkmdl"
    bl_label = 'Export PKMDL/ANI'
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = '.pkmdl'
    filter_glob: StringProperty(default='*.pkmdl', options={'HIDDEN'})

    fileformat: EnumProperty(
        name = 'Format',
        items = (('PKMDL', '(*.pkmdl)','Model'),('ANI','(*.ani)', 'Animation')),
        description = "Export format",
        default = 0,
        update = on_format_changed )

    use_optimize : BoolProperty( default = True )

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

    use_sort: BoolProperty( default = True )

    scale_factor: FloatProperty( default=1.0 )

    def info(self, msg='', icon=''):
        self.report({icon}, f'{self.fileformat} Export : ' + msg)

    def check(self, _context):
        old_filepath = self.filepath
        self.filepath = ensure_filepath_matches_format(
            self.filepath,
            self.fileformat,
        )
        return self.filepath != old_filepath

    def invoke(self, context, event):
        self.filter_glob = '*.pkmdl' if self.fileformat == 'PKMDL' else '*.ani'
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        from . import pk_export

        keywords = self.as_keywords(ignore=("axis_forward",
                                            "axis_up",
                                            "filter_glob",
                                            "fileformat",
                                            "check_existing",
                                            "sel_swt",
                                            ))

        global_matrix = axis_conversion(from_forward=self.axis_forward,
                                        from_up=self.axis_up,
                                        ).to_4x4()
        keywords["global_matrix"] = global_matrix

        common.info = self.info
        mdlexp.info = self.info
        pk_export.info = self.info
        return pk_export.load(self, context, **keywords)

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False
        self.layout.prop( self, 'fileformat' )
        if self.fileformat == 'PKMDL':
            header, body = self.layout.panel("MDL_export_include", default_closed=False)
            header.label( text="Include" )
            if body:                
                sublayout = body.column(heading="Limit to")
                sublayout.prop( self, "use_all" )
                sublayout.prop( self, "use_selection" )
                sublayout.prop( self, "use_visible" )


# Add to a menu
def menu_func_import(self, context):
    self.layout.operator(ImportMPK.bl_idname, text="Painkiller WorldMesh (.mpk/.dat)")


def menu_func_export(self, context):
    self.layout.operator(ExportMPK.bl_idname, text="Painkiller WorldMesh (.mpk/.dat)")


def menu_func_import_mdl(self, context):
    self.layout.operator(ImportMDL.bl_idname, text="Painkiller Model (.pkmdl/.ani)")


def menu_func_export_mdl(self, context):
    self.layout.operator(ExportMDL.bl_idname, text="Painkiller Model (.pkmdl/.ani)")


def register():
    bpy.utils.register_class(ImportMPK)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.utils.register_class(ExportMPK)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.utils.register_class(ImportMDL)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_mdl)
    bpy.utils.register_class(ExportMDL)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export_mdl)


def unregister():
    bpy.utils.unregister_class(ImportMPK)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(ExportMPK)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(ImportMDL)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_mdl)
    bpy.utils.unregister_class(ExportMDL)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export_mdl)


if __name__ == "__main__":
    register()
