# PK_tools

An add-on that imports Painkiller (PC game 2004) MPK geometry files.

> Tested on Blender 4.0.2.

## Installation via GUI

1. Download the latest plugin version from GitHub.
2. Create a ZIP archive that should contain the `io_scene_mpk` folder and the plugin python scripts inside:
```
io_scene_mpk\__init__.py
io_scene_mpk\import_mpk.py
```
3. In Blender, open `Edit` > `Preferences` and switch to the `Add-ons` section.
4. Select `Install an Add-on.` and select the ZIP archive that you created.
5. Search for the add-on in the list: enter `Painkiller MPK format` and enable it.
6. Save the preferences if you would like the script to always be enabled.

## Manual Installation

1. Download the latest plugin version from GitHub.
2. Put the unpacked `io_scene_mpk` folder with the python scripts to `C:\Program Files\Blender Foundation\Blender 4.0\4.0\scripts\addons`:

```
C:\Program Files\Blender Foundation\Blender 4.0\4.0\scripts\addons\io_scene_mpk\__init__.py
C:\Program Files\Blender Foundation\Blender 4.0\4.0\scripts\addons\io_scene_mpk\import_mpk.py
```

## Usage

Once the addon has been installed, you will be able to import Painkiller MPK geometry.

1. Extract a PKM or a PAK archive with the map geometry and textures.
2. Create a new folder and copy the MPK geometry file and all the map textures to that folder.
3. In Blender, delete the default scene: right-click on `Collection` > `Delete Hierarchy`.
4. Import Painkiller MPK geometry file via `File` > `Import` > `Painkiller World Mesh`.
5. Click `Shading` in Blender. Now you will be able to see a map with textures
6. If the map is too big to observe, you need to increase the `View End` distance in the 3D View area's `Properties` `N` menu > `View` tab. Consult the official Blender documentation.

## Uninstall via GUI

1. In Blender, open `Edit` > `Preferences` and switch to the `Add-ons` section.
2. Search for the `Painkiller MPK format` plugin.
3. Click on the `Display information` arrow and remove the plugin by clicking `Remove`.

## Uninstall manual

1. Remove the following files from the Blender folder:

```
C:\Program Files\Blender Foundation\Blender 4.0\4.0\scripts\addons\io_scene_mpk\__init__.py
C:\Program Files\Blender Foundation\Blender 4.0\4.0\scripts\addons\io_scene_mpk\import_mpk.py
```
