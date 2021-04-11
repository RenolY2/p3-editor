Pikmin 3 Generator and Path Editor
By Yoshi2

A 3D GUI editor for Pikmin 3's generator (object placement) and path files.
Pikmin 3 Deluxe is not officially supported at the moment so there may be issues with P3D.
Source: https://github.com/RenolY2/p3-editor
Releases: https://github.com/RenolY2/p3-editor/releases

File->Load: You can load generator files either from txt or from archived .szs files
(In Open File window click "Generator files (*.txt)" in bottom right and switch over 
to "Archived files (*.arc, *.szs)" to load generator files from archives.
When loading from an archive, a window will open for choosing the exact file you want to load.
File->Save:  When an archived file is loaded, "Save" saves into the same archive, otherwise it saves into the same text file.
File->Save As: Save the generator file at a different file location, or in the case of choosing a different szs file, a different archive.
When choosing a szs, the program will ask you which file inside the szs you want to overwrite.

Load->.OBJ: Load an .obj model to render as the environment in the editor
Load->.BJMP: Load a BJMP (Pikmin 3 collision file) to render as the environment in the editor. 
Can be loaded from a .szs archive or directly. If a szs has several BJMP files, all of them are loaded.

Paths->Load Paths: Load a path.txt which defines the carrying paths that Pikmin use to get back to the Ship/Onion.
Paths->Save Paths: Save the path to the last loaded Path file location, which can be an external txt file or a szs.
Paths->Save Paths As: Save the path to a different location, which can be an external txt file or a szs.

Misc->Go to object: Lists all objects in the current level. Double-Click on an object to teleport to it in the camera view.
Misc->Topdown View/3D View: Switch between the Top down view and the 3D view.

Ctrl+S will save both the generator file and the path file to their respective last loaded from places.

Controls
Top down view:
WASD - Move up/down/left/right. Hold shift to go faster.
Click and hold Middle mouse button and move mouse to move the view around.
Scroll wheel - Zoom in/out
Right-click to copy coordinates
Left-click to select objects, do a selection box, operate the gizmo or add an object.

3D View:
WASD - Move front/back/left/right
QE - Go up/down
Click and hold right mouse button to rotate camera 
Left-click to select objects, do a selection box, operate the gizmo or add an object.

Gizmo: Clicking and dragging the arrows moves the object in that direction.
Clicking and dragging the circles rotates the object. Move mouse around the object on the screen to rotate.


Add Object: Allows you to add new objects to the level. Objects are broken up into categories.
Select a category, then select an object in the category and then click "Add Object" at the bottom to go into 
"Add Object" mode where you left-click in the 3D view/Top down view to add the object. Press ESC to 
cancel the "Add Object" mode.
New object entries can be added in the Object Templates folder of the editor as text files. You will find that the subfolders
in that folder are equivalent to the categories you see in "Add Object".

Remove Objects: Delete all selected objects.

Ground Objects: Puts all selected objects on the ground. This requires a collision model to be loaded.

Edit Object: edits the settings of the selected object (only works if 1 object is selected). "Write Template" allows you to 
save the current object data as a text file. This works well with the "Add Object" feature mentioned above.

Ctrl+Z/Ctrl+Y for Undo/Redo. This undoes and redoes adding and deleting objects only.

In the editor's folder in resources/objectmodels/ you can place OBJ models named after the objects they should be applied to. Models with textures are supported.

Note: Due to the way object data parsing works, comments are not retained when editing an object's data.


============
Path Editor 

== Adding and removing waypoints ==
To add new path points, click on Add Object and choose Waypoint as the object category. Object template will be greyed out.
You can edit the waypoint radius, waypoint ID and waypoint type of the waypoint. You can then click on Add Object to add new waypoints
with those waypoint settings by clicking in the Topdown or 3D view

To remove path points, select them and click on Remove Object(s).
Waypoint removals and additions can be undone/redone with Ctrl+Y/Z, waypoint connections will be reverted.
Warning: In cases where undo/redo would cause a waypoint to have more than 8 links, incoming or outgoing, 
the link on the waypoint being undone/redone will be permanently removed to keep the limit of 8 links.

Clicking on "Add Path" will enter an "Add Path" mode where, starting with the waypoint you have currently selected, waypoints are connected 
in the order and direction that you are selecting them in, starting with the waypoint you have selected at the time you pressed "Add Path".
This makes it easy to create long paths. For connecting waypoints that should not all be connected in one line it is recommended to click "Add Path"
to leave the "Add Path" mode, then click on "Add Path" again. Shortcut: C 

Clicking on "Remove Path" will enter a "Remove Path" mode where waypoints are disconnected in the order and direction you are selecting them in.
This mode works similarly to "Add Path". Shortcut: R

When a waypoint is selected, its properties and the properties of its connections can be viewed and edited in the bottom right.
Node ID is usually empty but may be non-empty for some special path points, e.g. boss nodes.
Node Type defines a node as e.g. a geyser or a transition node.
The three fields for each link are Distance (probably), Link type, Unknown.
The editor synchronizes the outgoing Link type of a waypoint with the incoming Link type of the waypoint it's connected to, and vice versa.
Waypoints are recolored based on their type using the /resources/waypoint_node_colors.json file.

Path and Link types, courtesy of LazyBoii:
Warning: Info may be incomplete/inaccurate and doesn't cover all possible types.
More info may be found out in the future that can render this list outdated.

====PATH NODE TYPE====
Type 1 = Normal node, all Pikmin and leaders can take it
Type 8 = Another node for portal transition
Type 9 = Another node for portal transition
Type 16 = Slide node
Type 17 = Another Slide middle node
Type 33 = Another Geyser node
Type 128 = ???
Type 129 = ???
Type 137 = Node for portal transition
Type 144 = Another Slide node
Type 160 = Another Geyser node
Type 161 = Geyser node


LazyBoii's notes: 

- They may be even more type of node i did not cover and some node type may not be exact.
- Some node in Formidable Oak near the place where the plasm wraith leave the cave have in their id param "Boss00,01,02,03,04 and 05", there is maybe more node in the game that has different id.
- When a node is in a waterbox, only blue pikmin will be able to use it

====PATH LINK TYPE====
Link 0 = All Pikmin and leaders can take it
link 2 = Winged Pikmin link
Link 3 = Lily pad link
Link 5 = Only Pikmin walking/carrying golden nugget, bridges pieces, etc. or leader link
Link 6 = ???


=== Running from Source Code ===
Requirements: 
- Python >=3.6
- PyQt5
- numpy
- pyopengl

Run ``python pikmingen_editor.py``