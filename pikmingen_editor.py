import traceback
from copy import deepcopy
from timeit import default_timer
from io import TextIOWrapper, BytesIO, StringIO
import PyQt5.QtWidgets as QtWidgets
import PyQt5.QtCore as QtCore
from PyQt5.QtCore import Qt

from PyQt5.QtWidgets import (QWidget, QMainWindow, QFileDialog,
                             QSpacerItem, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QHBoxLayout,
                             QScrollArea, QGridLayout, QMenuBar, QMenu, QAction, QApplication, QStatusBar, QLineEdit)
from PyQt5.QtGui import QMouseEvent, QImage, QKeySequence
import PyQt5.QtGui as QtGui

import opengltext
import py_obj
from lib.model_rendering import Waterbox
from lib.libgen import GeneratorFile, GeneratorWriter


#from libpiktxt import PikminGenFile, WaterboxTxt
import widgets
from widgets.editor_widgets import catch_exception
from widgets.editor_widgets import AddPikObjectWindow
from configuration import read_config, make_default_config, save_cfg

import pikmingen_widgets as pikwidgets
from widgets.side_widget import PikminSideWidget
from widgets.editor_widgets import PikObjectEditor, open_error_dialog, catch_exception_with_dialog
from pikmingen_widgets import GenMapViewer, MODE_TOPDOWN
from lib.sarc import SARCArchive
from lib.libpath import Paths, Waypoint

from widgets.file_select import FileSelect

PIKMIN2GEN = "Generator files (defaultgen.txt;initgen.txt;plantsgen.txt;*.txt)"


class GenEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.pikmin_gen_file = GeneratorFile()

        self.setup_ui()

        try:
            self.configuration = read_config()
            print("Config file loaded")
        except FileNotFoundError as e:
            print("No config file found, creating default config...")
            self.configuration = make_default_config()

        self.pikmin_gen_view.pikmin_generators = self.pikmin_gen_file
        self.pikmin_gen_view.set_editorconfig(self.configuration["gen editor"])

        self.pathsconfig = self.configuration["default paths"]
        self.editorconfig = self.configuration["gen editor"]
        self.current_gen_path = None

        self.current_coordinates = None
        self.editing_windows = {}
        self.add_object_window = None
        self.object_to_be_added = None

        self.history = EditorHistory(20)
        self.edit_spawn_window = None

        self._window_title = ""
        self._user_made_change = False
        self._justupdatingselectedobject = False

        self.addobjectwindow_last_selected = None

        #self.loaded_archive = None
        self.loaded_archive_file = None
        self.loaded_paths = Paths()
        self.path_file_path = None
        self.pikmin_gen_view.waypoints.set_paths(self.loaded_paths)

        self.last_waypoint = None
        self.last_gen_path = self.pathsconfig["gen"]
        self.last_path_path = self.pathsconfig["gen"]
        self.last_gen_filter = ""
        self.last_path_filter = ""

    @catch_exception
    def reset(self):
        self.last_waypoint = None
        self.loaded_archive = None
        self.loaded_archive_file = None
        self.history.reset()
        self.object_to_be_added = None
        self.pikmin_gen_view.reset(keep_collision=True)

        self.current_coordinates = None
        for key, val in self.editing_windows.items():
            val.destroy()

        self.editing_windows = {}

        if self.add_object_window is not None:
            self.add_object_window.destroy()
            self.add_object_window = None

        if self.edit_spawn_window is not None:
            self.edit_spawn_window.destroy()
            self.edit_spawn_window = None

        self.current_gen_path = None
        self.pik_control.reset_info()
        self.pik_control.button_add_object.setChecked(False)
        #self.pik_control.button_move_object.setChecked(False)
        self._window_title = ""
        self._user_made_change = False

        self.addobjectwindow_last_selected = None
        self.addobjectwindow_last_selected_category = None

    def set_base_window_title(self, name):
        self._window_title = name
        if name != "":
            self.setWindowTitle("Pikmin 3 Generators Editor - "+name)
        else:
            self.setWindowTitle("Pikmin 3 Generators Editor")

    def set_has_unsaved_changes(self, hasunsavedchanges):
        if hasunsavedchanges and not self._user_made_change:
            self._user_made_change = True

            if self._window_title != "":
                self.setWindowTitle("Pikmin 3 Generators Editor [Unsaved Changes] - " + self._window_title)
            else:
                self.setWindowTitle("Pikmin 3 Generators Editor [Unsaved Changes] ")
        elif not hasunsavedchanges and self._user_made_change:
            self._user_made_change = False
            if self._window_title != "":
                self.setWindowTitle("Pikmin 3 Generators Editor - " + self._window_title)
            else:
                self.setWindowTitle("Pikmin 3 Generators Editor")

    def gen_path_combined_saving(self):
        self.button_save_level()
        self.button_save_paths()

    def setup_ui(self):
        self.resize(1000, 800)
        self.set_base_window_title("")

        self.setup_ui_menubar()
        self.setup_ui_toolbar()

        self.centralwidget = QWidget(self)
        self.centralwidget.setObjectName("centralwidget")
        self.setCentralWidget(self.centralwidget)

        self.pikmin_gen_view = GenMapViewer(self.centralwidget)
        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.horizontalLayout.addWidget(self.pikmin_gen_view)

        spacerItem = QSpacerItem(10, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.horizontalLayout.addItem(spacerItem)

        self.pik_control = PikminSideWidget(self)
        self.horizontalLayout.addWidget(self.pik_control)

        QtWidgets.QShortcut(Qt.Key_C, self).activated.connect(self.action_connect_button_pressed_shortcut)
        QtWidgets.QShortcut(Qt.Key_R, self).activated.connect(self.action_disconnect_button_pressed_shortcut)


        QtWidgets.QShortcut(Qt.CTRL + Qt.Key_E, self).activated.connect(self.action_open_editwindow_shortcut)
        QtWidgets.QShortcut(Qt.Key_M, self).activated.connect(self.shortcut_move_objects)
        QtWidgets.QShortcut(Qt.Key_G, self).activated.connect(self.action_ground_objects)
        QtWidgets.QShortcut(Qt.CTRL + Qt.Key_A, self).activated.connect(self.shortcut_open_add_item_window)
        self.statusbar = QStatusBar(self)
        self.statusbar.setObjectName("statusbar")
        self.setStatusBar(self.statusbar)

        self.connect_actions()

    @catch_exception_with_dialog
    def setup_ui_menubar(self):
        self.menubar = QMenuBar(self)
        self.file_menu = QMenu(self)
        self.file_menu.setTitle("File")

        self.save_file_shortcut = QtWidgets.QShortcut(QKeySequence("Ctrl+S"), self)
        self.save_file_shortcut.activated.connect(self.gen_path_combined_saving)
        #QtWidgets.QShortcut(Qt.CTRL + Qt.Key_O, self.file_menu).activated.connect(self.button_load_level)
        #QtWidgets.QShortcut(Qt.CTRL + Qt.Key_Alt + Qt.Key_S, self.file_menu).activated.connect(self.button_save_level_as)

        self.file_load_action = QAction("Load", self)
        self.save_file_action = QAction("Save", self)
        self.save_file_action.setStatusTip("Save Shortcut: Ctrl+S")
        self.save_file_action.setShortcutVisibleInContextMenu(True)
        self.save_file_as_action = QAction("Save As", self)
        #self.save_file_action.setShortcut("Ctrl+S")
        self.file_load_action.setShortcut("Ctrl+O")
        self.save_file_as_action.setShortcut("Ctrl+Alt+S")

        self.file_load_action.triggered.connect(self.button_load_level)
        self.save_file_action.triggered.connect(self.button_save_level)
        self.save_file_as_action.triggered.connect(self.button_save_level_as)

        self.file_menu.addAction(self.file_load_action)
        self.file_menu.addAction(self.save_file_action)
        self.file_menu.addAction(self.save_file_as_action)

        self.paths_menu = QMenu(self.menubar)
        self.paths_menu.setTitle("Paths")
        self.paths_load = QAction("Load Paths", self)
        self.paths_load.triggered.connect(self.button_load_paths)
        self.paths_menu.addAction(self.paths_load)
        self.paths_save = QAction("Save Paths", self)
        self.paths_save.triggered.connect(self.button_save_paths)
        self.paths_save.setStatusTip("Save Shortcut: Ctrl+S")
        #self.paths_save.setShortcut("Ctrl+S")
        self.paths_menu.addAction(self.paths_save)
        self.paths_save_as = QAction("Save Paths As", self)
        self.paths_save_as.triggered.connect(self.button_save_paths_as)
        self.paths_menu.addAction(self.paths_save_as)

        # ------ Collision Menu
        self.collision_menu = QMenu(self.menubar)
        self.collision_menu.setTitle("Geometry")
        self.collision_load_action = QAction("Load .OBJ", self)
        self.collision_load_action.triggered.connect(self.button_load_collision)
        self.collision_menu.addAction(self.collision_load_action)
        self.collision_load_grid_action = QAction("Load BJMP", self)
        self.collision_load_grid_action.triggered.connect(self.button_load_collision_bjmp)
        self.collision_menu.addAction(self.collision_load_grid_action)


        # Misc
        self.misc_menu = QMenu(self.menubar)
        self.misc_menu.setTitle("Misc")
        #self.spawnpoint_action = QAction("Set startPos/Dir", self)
        #self.spawnpoint_action.triggered.connect(self.action_open_rotationedit_window)
        #self.misc_menu.addAction(self.spawnpoint_action)
        self.goto_action = QAction("Go to Object", self)
        self.goto_action.triggered.connect(self.do_goto_action)
        self.goto_action.setShortcut("Ctrl+G")

        self.misc_menu.addAction(self.goto_action)

        self.change_to_topdownview_action = QAction("Topdown View", self)
        self.change_to_topdownview_action.triggered.connect(self.change_to_topdownview)
        self.misc_menu.addAction(self.change_to_topdownview_action)
        self.change_to_topdownview_action.setCheckable(True)
        self.change_to_topdownview_action.setChecked(True)
        self.change_to_topdownview_action.setShortcut("Ctrl+1")

        self.change_to_3dview_action = QAction("3D View", self)
        self.change_to_3dview_action.triggered.connect(self.change_to_3dview)
        self.misc_menu.addAction(self.change_to_3dview_action)
        self.change_to_3dview_action.setCheckable(True)
        self.change_to_3dview_action.setShortcut("Ctrl+2")

        self.menubar.addAction(self.file_menu.menuAction())
        self.menubar.addAction(self.collision_menu.menuAction())
        self.menubar.addAction(self.paths_menu.menuAction())
        self.menubar.addAction(self.misc_menu.menuAction())
        self.setMenuBar(self.menubar)


        self.last_obj_select_pos = 0

    @catch_exception_with_dialog
    def do_goto_action(self, a):
        namecount = {}
        objlist = {}

        for obj in self.pikmin_gen_file.generators:
            if obj.name not in namecount:
                namecount[obj.name] = 1
                name = obj.name+" (1)"
                objlist[name] = obj
            else:
                namecount[obj.name] += 1
                name = obj.name+" ({0})".format(namecount[obj.name])
                objlist[name] = obj

        choice, pos = FileSelect.open_file_list(self, sorted(objlist.keys(), key=lambda x: x.lower()),
                                           "Select Object", self.last_obj_select_pos)

        if choice is not None:
            self.last_obj_select_pos = pos
            obj = objlist[choice]


            self.pikmin_gen_view.selected = [obj]
            self.pikmin_gen_view.gizmo.position.x = obj.position.x
            self.pikmin_gen_view.gizmo.position.y = obj.position.y
            self.pikmin_gen_view.gizmo.position.z = obj.position.z

            self.pikmin_gen_view.select_update.emit()
            if self.pikmin_gen_view.mode == MODE_TOPDOWN:
                self.pikmin_gen_view.offset_z = -obj.position.z
                self.pikmin_gen_view.offset_x = -obj.position.x
            else:
                look = self.pikmin_gen_view.camera_direction.copy()

                pos = obj.position.copy()
                fac = 200
                self.pikmin_gen_view.offset_z = -(pos.z + look.y*fac)
                self.pikmin_gen_view.offset_x = pos.x - look.x*fac
                self.pikmin_gen_view.camera_height = pos.y - look.z*fac

    def change_to_topdownview(self):
        self.pikmin_gen_view.change_from_3d_to_topdown()
        self.change_to_topdownview_action.setChecked(True)
        self.change_to_3dview_action.setChecked(False)

    def change_to_3dview(self):
        self.pikmin_gen_view.change_from_topdown_to_3d()
        self.change_to_topdownview_action.setChecked(False)
        self.change_to_3dview_action.setChecked(True)
        self.statusbar.clearMessage()

    def setup_ui_toolbar(self):
        # self.toolbar = QtWidgets.QToolBar("Test", self)
        # self.toolbar.addAction(QAction("TestToolbar", self))
        # self.toolbar.addAction(QAction("TestToolbar2", self))
        # self.toolbar.addAction(QAction("TestToolbar3", self))

        # self.toolbar2 = QtWidgets.QToolBar("Second Toolbar", self)
        # self.toolbar2.addAction(QAction("I like cake", self))

        # self.addToolBar(self.toolbar)
        # self.addToolBarBreak()
        # self.addToolBar(self.toolbar2)
        pass

    def connect_actions(self):
        self.pikmin_gen_view.select_update.connect(self.action_update_info)
        self.pik_control.lineedit_coordinatex.textChanged.connect(self.create_field_edit_action("coordinatex"))
        self.pik_control.lineedit_coordinatey.textChanged.connect(self.create_field_edit_action("coordinatey"))
        self.pik_control.lineedit_coordinatez.textChanged.connect(self.create_field_edit_action("coordinatez"))

        self.pik_control.lineedit_rotationx.textChanged.connect(self.create_field_edit_action("rotationx"))
        self.pik_control.lineedit_rotationy.textChanged.connect(self.create_field_edit_action("rotationy"))
        self.pik_control.lineedit_rotationz.textChanged.connect(self.create_field_edit_action("rotationz"))

        self.pikmin_gen_view.position_update.connect(self.action_update_position)

        self.pikmin_gen_view.customContextMenuRequested.connect(self.mapview_showcontextmenu)
        self.pik_control.button_edit_object.pressed.connect(self.action_open_editwindow)

        self.pik_control.button_add_object.pressed.connect(self.button_open_add_item_window)
        #self.pik_control.button_move_object.pressed.connect(self.button_move_objects)
        self.pikmin_gen_view.move_points.connect(self.action_move_objects)
        self.pikmin_gen_view.height_update.connect(self.action_change_object_heights)
        self.pikmin_gen_view.create_waypoint.connect(self.action_add_object)
        self.pikmin_gen_view.create_waypoint_3d.connect(self.action_add_object_3d)
        self.pik_control.button_ground_object.pressed.connect(self.action_ground_objects)
        self.pik_control.button_remove_object.pressed.connect(self.action_delete_objects)

        delete_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(Qt.Key_Delete), self)
        delete_shortcut.activated.connect(self.action_delete_objects)

        undo_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(Qt.CTRL + Qt.Key_Z), self)
        undo_shortcut.activated.connect(self.action_undo)

        redo_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(Qt.CTRL + Qt.Key_Y), self)
        redo_shortcut.activated.connect(self.action_redo)

        self.pikmin_gen_view.rotate_current.connect(self.action_rotate_object)

        #delete_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(Qt.Key_Delete), self)
        #delete_shortcut.activated.connect(self.action_delete_objects)


        self.pik_control.button_connect.pressed.connect(self.action_connect_button_pressed)
        self.pik_control.button_disconnect.pressed.connect(self.action_disconnect_button_pressed)

    def action_open_rotationedit_window(self):
        if self.edit_spawn_window is None:
            self.edit_spawn_window = pikwidgets.SpawnpointEditor()
            self.edit_spawn_window.position.setText("{0}, {1}, {2}".format(
                self.pikmin_gen_file.startpos_x, self.pikmin_gen_file.startpos_y, self.pikmin_gen_file.startpos_z
            ))
            self.edit_spawn_window.rotation.setText(str(self.pikmin_gen_file.startdir))
            self.edit_spawn_window.closing.connect(self.action_close_edit_startpos_window)
            self.edit_spawn_window.button_savetext.pressed.connect(self.action_save_startpos)
            self.edit_spawn_window.show()

    #@catch_exception
    def button_load_level(self):
        filepath, choosentype = QFileDialog.getOpenFileName(
            self, "Open File",
            self.last_gen_path,
            "Generator files (*.txt);;Archived files (*.arc, *.szs);;All files (*)",
            self.last_gen_filter)

        if filepath:
            print("Resetting editor")
            self.reset()
            print("Reset done")
            print("Chosen file type:", choosentype)
            self.last_gen_filter = choosentype
            self.last_gen_path = filepath
            if choosentype == "Archived files (*.arc, *.szs)" or filepath.endswith(".szs") or filepath.endswith(".arc"):
                with open(filepath, "rb") as f:
                    try:
                        arc = SARCArchive.from_file(f)
                    except Exception as error:
                        print("Error appeared while loading:", error)
                        traceback.print_exc()
                        open_error_dialog(str(error), self)
                        return
                filepaths = [x for x in arc.files.keys()]
                filepaths.sort()
                file, lastpos = FileSelect.open_file_list(self, filepaths, title="Select file")
                print("selected:", file)
                self.loaded_archive_file = file

                if file is None:
                    self.loaded_archive = None
                    return

                genfile = arc.files[file]

                try:
                    pikmin_gen_file = GeneratorFile.from_file(
                        TextIOWrapper(BytesIO(genfile.getvalue()), errors="replace")
                    )
                    genfile.seek(0)
                    self.setup_gen_file(pikmin_gen_file, filepath, file)

                except Exception as error:
                    print("Error appeared while loading:", error)
                    traceback.print_exc()
                    open_error_dialog(str(error), self)

            else:
                with open(filepath, "r", encoding="shift-jis-2004", errors="replace") as f:
                    try:
                        pikmin_gen_file = GeneratorFile.from_file(f)
                        self.setup_gen_file(pikmin_gen_file, filepath)

                    except Exception as error:
                        print("Error appeared while loading:", error)
                        traceback.print_exc()
                        open_error_dialog(str(error), self)

    def button_load_paths(self):
        filepath, choosentype = QFileDialog.getOpenFileName(
            self, "Open File",
            self.last_path_path,
            "Path file (path.txt;*.txt);;Archived Path file (*.szs);;All files (*)",
            self.last_path_filter)

        if filepath:
            self.last_path_path = filepath
            self.last_path_filter = choosentype
            if filepath.lower().endswith(".arc") or filepath.lower().endswith(".szs") or choosentype == "Archived Path file (*.szs)":
                with open(filepath, "rb") as f:
                    try:
                        arc = SARCArchive.from_file(f)
                    except Exception as error:
                        print("Error appeared while loading:", error)
                        traceback.print_exc()
                        open_error_dialog(str(error), self)
                        return

                if "path.txt" not in arc.files:
                    open_error_dialog("SZS Archive does not contain 'path.txt'! Path file not loaded.", self)
                    return

                try:
                    path_raw = arc.files["path.txt"].getvalue()
                    arc.files["path.txt"].seek(0)
                    path_file = TextIOWrapper(BytesIO(path_raw), errors="replace")
                    paths = Paths.from_file(path_file)
                    self.loaded_paths = paths
                    self.pikmin_gen_view.waypoints.set_paths(self.loaded_paths)
                    self.pikmin_gen_view.do_redraw()

                except Exception as error:
                    print("Error appeared while loading:", error)
                    traceback.print_exc()
                    open_error_dialog(str(error), self)

                """filepaths = [x for x in self.loaded_archive.files.keys()]
                filepaths.sort()
                file, lastpos = FileSelect.open_file_list(self, filepaths, title="Select file")
                print("selected:", file)
                self.loaded_archive_file = file"""

            elif filepath.lower().endswith(".txt"):
                with open(filepath, "r", encoding="shift_jis-2004") as f:
                    try:
                        paths = Paths.from_file(f)
                        self.loaded_paths = paths
                        self.pikmin_gen_view.waypoints.set_paths(self.loaded_paths)
                        self.pikmin_gen_view.do_redraw()

                    except Exception as error:
                        print("Error appeared while loading:", error)
                        traceback.print_exc()
                        open_error_dialog(str(error), self)

            self.path_file_path = filepath

    def button_save_paths(self):
        filepath = self.path_file_path

        if filepath:
            if filepath.lower().endswith(".arc") or filepath.lower().endswith(".szs"):
                with open(filepath, "rb") as f:
                    try:
                        arc = SARCArchive.from_file(f)
                    except Exception as error:
                        print("Error appeared while loading:", error)
                        traceback.print_exc()
                        open_error_dialog(str(error), self)
                        return

                if "path.txt" not in arc.files:
                    open_error_dialog("SZS Archive does not contain 'path.txt'! Path file not saved.", self)
                    return

                try:
                    path_raw = arc.files["path.txt"].getvalue()
                    arc.files["path.txt"].seek(0)
                    tmp = StringIO()
                    self.loaded_paths.write(tmp)
                    arc.files["path.txt"].write(tmp.getvalue().encode(encoding="shift-jis-2004", errors="backslashreplace"))
                    arc.files["path.txt"].seek(0)

                    with open(filepath, "wb") as f:
                        arc.to_file(f, compress=filepath.endswith(".szs"))

                    #self.set_has_unsaved_changes(False)
                    self.statusbar.showMessage("Saved to {0}".format(filepath))
                except Exception as error:
                    print("Error appeared while loading:", error)
                    traceback.print_exc()
                    open_error_dialog(str(error), self)

            elif filepath.lower().endswith(".txt"):
                with open(filepath, "w", encoding="shift_jis-2004") as f:
                    self.loaded_paths.write(f)
                    #self.set_has_unsaved_changes(False)

                    self.statusbar.showMessage("Saved to {0}".format(self.current_gen_path))

    def button_save_paths_as(self):
        filepath, choosentype = QFileDialog.getSaveFileName(
            self, "Save File",
            self.last_path_path,
            "Generator files (*.txt);;Archived files (*.arc, *.szs);;All files (*)",
            self.last_path_filter)

        if filepath:
            if filepath.lower().endswith(".arc") or filepath.lower().endswith(".szs"):
                with open(filepath, "rb") as f:
                    try:
                        arc = SARCArchive.from_file(f)
                    except Exception as error:
                        print("Error appeared while loading:", error)
                        traceback.print_exc()
                        open_error_dialog(str(error), self)
                        return

                if "path.txt" not in arc.files:
                    open_error_dialog("SZS Archive does not contain 'path.txt'! Path file not saved.", self)
                    return

                try:
                    path_raw = arc.files["path.txt"].getvalue()
                    arc.files["path.txt"].seek(0)
                    tmp = StringIO()
                    self.loaded_paths.write(tmp)
                    arc.files["path.txt"].write(
                        tmp.getvalue().encode(encoding="shift-jis-2004", errors="backslashreplace"))
                    arc.files["path.txt"].seek(0)

                    with open(filepath, "wb") as f:
                        arc.to_file(f, compress=filepath.endswith(".szs"))

                    # self.set_has_unsaved_changes(False)
                    self.statusbar.showMessage("Saved to {0}".format(filepath))
                except Exception as error:
                    print("Error appeared while loading:", error)
                    traceback.print_exc()
                    open_error_dialog(str(error), self)

            elif filepath.lower().endswith(".txt"):
                with open(filepath, "w", encoding="shift_jis-2004") as f:
                    self.loaded_paths.write(f)
                    # self.set_has_unsaved_changes(False)

                    self.statusbar.showMessage("Saved to {0}".format(self.current_gen_path))

            self.path_file_path = filepath

    def setup_gen_file(self, pikmin_gen_file, filepath, name_in_szs=None):
        self.pikmin_gen_file = pikmin_gen_file
        self.pikmin_gen_view.pikmin_generators = self.pikmin_gen_file
        # self.pikmin_gen_view.update()
        self.pikmin_gen_view.do_redraw()

        print("File loaded")
        # self.bw_map_screen.update()
        # path_parts = path.split(filepath)
        if name_in_szs is not None:
            self.set_base_window_title(filepath+" ({0})".format(name_in_szs))
        else:
            self.set_base_window_title(filepath)
        self.pathsconfig["gen"] = filepath
        save_cfg(self.configuration)
        self.current_gen_path = filepath

    @catch_exception_with_dialog
    def button_save_level(self, *args, **kwargs):
        if self.current_gen_path is not None:
            if self.current_gen_path.lower().endswith(".arc") or self.current_gen_path.lower().endswith(".szs"):
                with open(self.current_gen_path, "rb") as f:
                    arc = SARCArchive.from_file(f)
                #assert self.loaded_archive_file is not None



                file = arc.files[self.loaded_archive_file]
                file.seek(0)
                tmp = StringIO()
                writer = GeneratorWriter(tmp)
                self.pikmin_gen_file.write(writer)
                file.write(tmp.getvalue().encode(encoding="shift-jis-2004", errors="backslashreplace"))
                file.seek(0)

                with open(self.current_gen_path, "wb") as f:
                    arc.to_file(f, compress=self.current_gen_path.endswith(".szs"))

                self.set_has_unsaved_changes(False)
                self.statusbar.showMessage("Saved to {0}".format(self.current_gen_path))

            else:
                with open(self.current_gen_path, "w", encoding="shift-jis-2004", errors="backslashreplace") as f:
                    writer = GeneratorWriter(f)
                    self.pikmin_gen_file.write(writer)
                    self.set_has_unsaved_changes(False)

                    self.statusbar.showMessage("Saved to {0}".format(self.current_gen_path))
        #else:
        #    self.button_save_level_as()

    @catch_exception_with_dialog
    def button_save_level_as(self, *args, **kwargs):
        filepath, choosentype = QFileDialog.getSaveFileName(
            self, "Save File",
            self.last_gen_path,
            "Generator files (*.txt);;Archived files (*.arc, *.szs);;All files (*)",
            self.last_gen_filter)
        if filepath:
            self.last_gen_path = filepath
            self.last_gen_filter = choosentype
            if choosentype == "Archived files (*.arc, *.szs)" or filepath.endswith(".arc") or filepath.endswith(".szs"):
                with open(filepath, "rb") as f:
                    arc = SARCArchive.from_file(f)

                filepaths = [x for x in arc.files.keys()]
                filepaths.sort()
                filen, lastpos = FileSelect.open_file_list(self, filepaths, title="Select file to save over")
                print("selected:", filen)
                self.loaded_archive_file = filen

                if filen is None:
                    return

                file = arc.files[filen]
                file.seek(0)
                tmp = StringIO()
                writer = GeneratorWriter(tmp)
                self.pikmin_gen_file.write(writer)
                file.write(tmp.getvalue().encode(encoding="shift-jis-2004", errors="backslashreplace"))
                file.seek(0)
                with open(filepath, "wb") as f:
                    arc.to_file(f, compress=filepath.endswith(".szs"))

                self.set_has_unsaved_changes(False)
                self.statusbar.showMessage("Saved to {0}".format(filepath))
                self.set_base_window_title(filepath+" ({0})".format(filen))
                self.pathsconfig["gen"] = filepath
                save_cfg(self.configuration)
                self.current_gen_path = filepath
            else:
                with open(filepath, "w", encoding="shift-jis-2004", errors="backslashreplace") as f:

                    writer = GeneratorWriter(f)
                    self.pikmin_gen_file.write(writer)
                    self.set_base_window_title(filepath)
                    self.pathsconfig["gen"] = filepath
                    save_cfg(self.configuration)
                    self.current_gen_path = filepath
                    self.set_has_unsaved_changes(False)
                self.loaded_archive_file = None

            self.statusbar.showMessage("Saved to {0}".format(self.current_gen_path))

    def button_load_collision(self):
        try:
            filepath, choosentype = QFileDialog.getOpenFileName(
                self, "Open File",
                self.pathsconfig["collision"],
                "Collision (*.obj);;All files (*)")

            if not filepath:
                return

            with open(filepath, "r") as f:
                verts, faces, normals = py_obj.read_obj(f)

            self.setup_collision(verts, faces, filepath)

        except Exception as e:
            traceback.print_exc()
            open_error_dialog(str(e), self)

    def button_load_collision_bjmp(self):
        try:
            filepath, choosentype = QFileDialog.getOpenFileName(
                self, "Open File",
                self.pathsconfig["collision"],
                "Pikmin 3 Archive (*.szs);;Pikmin 3 Map Collision (*.bjmp);;All files (*)")
            if filepath:
                if choosentype == "Pikmin 3 Archive (*.szs)" or filepath.endswith(".szs"):
                    with open(filepath, "rb") as f:
                        sarc = SARCArchive.from_file(f)
                    verts = []
                    faces = []

                    for path, file in sarc.files.items():
                        if path.endswith(".bjmp"):
                            collision = py_obj.BJMP(file)
                            offset = len(verts)
                            for v1,v2,v3 in collision.triangles:
                                faces.append((v1+offset, v2+offset, v3+offset))
                            verts.extend(collision.vertices)
                    del sarc

                else:
                    with open(filepath, "rb") as f:
                        collision = py_obj.BJMP(f)

                    verts = collision.vertices
                    faces = collision.triangles #[face for face in collision.faces]

                self.setup_collision(verts, faces, filepath)

        except Exception as e:
            traceback.print_exc()
            open_error_dialog(str(e), self)

    def setup_collision(self, verts, faces, filepath):
        self.pikmin_gen_view.set_collision(verts, faces)
        self.pathsconfig["collision"] = filepath
        save_cfg(self.configuration)

    def action_close_edit_startpos_window(self):
        self.edit_spawn_window.destroy()
        self.edit_spawn_window = None

    @catch_exception_with_dialog
    def action_save_startpos(self):
        pos, direction = self.edit_spawn_window.get_pos_dir()
        self.pikmin_gen_file.startpos_x = pos[0]
        self.pikmin_gen_file.startpos_y = pos[1]
        self.pikmin_gen_file.startpos_z = pos[2]
        self.pikmin_gen_file.startdir = direction

        #self.pikmin_gen_view.update()
        self.pikmin_gen_view.do_redraw()
        self.set_has_unsaved_changes(True)

    def button_open_add_item_window(self):
        if self.add_object_window is None:
            self.add_object_window = AddPikObjectWindow()
            self.add_object_window.button_savetext.pressed.connect(self.button_add_item_window_save)
            self.add_object_window.closing.connect(self.button_add_item_window_close)
            if self.addobjectwindow_last_selected is not None:
                self.add_object_window.category_menu.setCurrentIndex(self.addobjectwindow_last_selected_category)
                self.add_object_window.template_menu.setCurrentIndex(self.addobjectwindow_last_selected)

            self.add_object_window.show()

        elif self.pikmin_gen_view.mousemode == pikwidgets.MOUSE_MODE_ADDWP:
            self.pikmin_gen_view.set_mouse_mode(pikwidgets.MOUSE_MODE_NONE)
            self.pik_control.button_add_object.setChecked(False)

    def shortcut_open_add_item_window(self):
        if self.add_object_window is None:
            self.add_object_window = AddPikObjectWindow()
            self.add_object_window.button_savetext.pressed.connect(self.button_add_item_window_save)
            self.add_object_window.closing.connect(self.button_add_item_window_close)
            if self.addobjectwindow_last_selected is not None:
                self.add_object_window.category_menu.setCurrentIndex(self.addobjectwindow_last_selected_category)
                self.add_object_window.template_menu.setCurrentIndex(self.addobjectwindow_last_selected)


            self.add_object_window.show()

    @catch_exception
    def button_add_item_window_save(self):
        if self.add_object_window is not None:
            self.object_to_be_added = self.add_object_window.get_content()

            if self.object_to_be_added is not None:
                self.addobjectwindow_last_selected_category = self.add_object_window.category_menu.currentIndex()
                self.addobjectwindow_last_selected = self.add_object_window.template_menu.currentIndex()
                self.pik_control.button_add_object.setChecked(True)
                #self.pik_control.button_move_object.setChecked(False)
                self.pikmin_gen_view.set_mouse_mode(pikwidgets.MOUSE_MODE_ADDWP)
                self.add_object_window.destroy()
                self.add_object_window = None
                #self.pikmin_gen_view.setContextMenuPolicy(Qt.DefaultContextMenu)


    @catch_exception
    def button_add_item_window_close(self):
        # self.add_object_window.destroy()
        self.add_object_window = None
        self.pik_control.button_add_object.setChecked(False)
        self.pikmin_gen_view.set_mouse_mode(pikwidgets.MOUSE_MODE_NONE)

    @catch_exception
    def action_add_object(self, x, z):
        if isinstance(self.object_to_be_added, Waypoint):
            newobj = deepcopy(self.object_to_be_added)
        else:
            newobj = self.object_to_be_added.copy()
        newobj.position.x = x
        newobj.position.z = z

        if self.editorconfig.getboolean("GroundObjectsWhenAdding") is True:
            if self.pikmin_gen_view.collision is not None:
                y = self.pikmin_gen_view.collision.collide_ray_downwards(x, z)
                if y is not None:
                    newobj.position.y = y
        if isinstance(newobj, Waypoint):
            self.pikmin_gen_view.waypoints.paths.waypoints.append(newobj)
            newobj._wp_list = self.pikmin_gen_view.waypoints.paths.waypoints
        else:
            self.pikmin_gen_file.generators.append(newobj)
        #self.pikmin_gen_view.update()
        self.pikmin_gen_view.do_redraw()
        self.pikmin_gen_view.waypoints.set_paths_dirty()

        self.history.add_history_addobject(newobj)
        self.set_has_unsaved_changes(True)

    @catch_exception
    def action_add_object_3d(self, x, y, z):
        if isinstance(self.object_to_be_added, Waypoint):
            newobj = deepcopy(self.object_to_be_added)
        else:
            newobj = self.object_to_be_added.copy()

        newobj.position.x = round(x, 6)
        newobj.position.y = round(y, 6)
        newobj.position.z = round(z, 6)
        #newobj.offset_x = newobj.offset_y = newobj.offset_z = 0.0
        if isinstance(newobj, Waypoint):
            self.pikmin_gen_view.waypoints.paths.waypoints.append(newobj)
            newobj._wp_list = self.pikmin_gen_view.waypoints.paths.waypoints
        else:
            self.pikmin_gen_file.generators.append(newobj)
        # self.pikmin_gen_view.update()
        self.pikmin_gen_view.do_redraw()
        self.pikmin_gen_view.waypoints.set_paths_dirty()

        self.history.add_history_addobject(newobj)
        self.set_has_unsaved_changes(True)

    def button_move_objects(self):
        if self.pikmin_gen_view.mousemode == pikwidgets.MOUSE_MODE_MOVEWP:
            self.pikmin_gen_view.set_mouse_mode(pikwidgets.MOUSE_MODE_NONE)
            #self.pik_control.button_move_object.setChecked(False)

        else:
            self.pikmin_gen_view.set_mouse_mode(pikwidgets.MOUSE_MODE_MOVEWP)
            self.pik_control.button_add_object.setChecked(False)
            #self.pik_control.button_move_object.setChecked(True)

    def shortcut_move_objects(self):
        if self.pikmin_gen_view.mousemode == pikwidgets.MOUSE_MODE_MOVEWP:
            self.pikmin_gen_view.set_mouse_mode(pikwidgets.MOUSE_MODE_NONE)
            #self.pik_control.button_move_object.setChecked(False)

        else:
            self.pikmin_gen_view.set_mouse_mode(pikwidgets.MOUSE_MODE_MOVEWP)
            self.pik_control.button_add_object.setChecked(False)
            #self.pik_control.button_move_object.setChecked(True)


    @catch_exception
    def action_move_objects(self, deltax, deltay, deltaz):
        updatePaths = False
        for obj in self.pikmin_gen_view.selected:
            """obj.x += deltax
            obj.z += deltaz
            obj.x = round(obj.x, 6)
            obj.z = round(obj.z, 6)
            obj.position_x = obj.x
            obj.position_z = obj.z
            obj.offset_x = 0
            obj.offset_z = 0

            if self.editorconfig.getboolean("GroundObjectsWhenMoving") is True:
                if self.pikmin_gen_view.collision is not None:
                    y = self.pikmin_gen_view.collision.collide_ray_downwards(obj.x, obj.z)
                    obj.y = obj.position_y = round(y, 6)
                    obj.offset_y = 0"""
            obj.position.x += deltax
            obj.position.y += deltay
            obj.position.z += deltaz
            if isinstance(obj, Waypoint):
                updatePaths = True

        if len(self.pikmin_gen_view.selected) == 1:
            obj = self.pikmin_gen_view.selected[0]
            if hasattr(obj, "rotation"):
                self.pik_control.set_info(self.update_3d, obj, obj.position, obj.rotation)
            else:
                self.pik_control.set_info(self.update_3d, obj, obj.position, None)


        #self.pikmin_gen_view.update()
        if updatePaths:
            self.pikmin_gen_view.waypoints.set_dirty()
        self.pikmin_gen_view.do_redraw()
        self.set_has_unsaved_changes(True)


    @catch_exception
    def action_change_object_heights(self, deltay):
        for obj in self.pikmin_gen_view.selected:
            obj.y += deltay
            obj.y = round(obj.y, 6)
            obj.position_y = obj.y
            obj.offset_y = 0

        if len(self.pikmin_gen_view.selected) == 1:
            obj = self.pikmin_gen_view.selected[0]
            self.pik_control.set_info(self.update_3d, obj, (obj.x, obj.y, obj.z), obj.get_rotation())

        #self.pikmin_gen_view.update()
        self.pikmin_gen_view.do_redraw()
        self.set_has_unsaved_changes(True)

    def keyPressEvent(self, event: QtGui.QKeyEvent):

        if event.key() == Qt.Key_Escape:
            self.pikmin_gen_view.set_mouse_mode(pikwidgets.MOUSE_MODE_NONE)
            self.pik_control.button_add_object.setChecked(False)
            #self.pik_control.button_move_object.setChecked(False)
            if self.add_object_window is not None:
                self.add_object_window.close()

        if event.key() == Qt.Key_Shift:
            self.pikmin_gen_view.shift_is_pressed = True
        elif event.key() == Qt.Key_R:
            self.pikmin_gen_view.rotation_is_pressed = True
        elif event.key() == Qt.Key_H:
            self.pikmin_gen_view.change_height_is_pressed = True

        if event.key() == Qt.Key_W:
            self.pikmin_gen_view.MOVE_FORWARD = 1
        elif event.key() == Qt.Key_S:
            self.pikmin_gen_view.MOVE_BACKWARD = 1
        elif event.key() == Qt.Key_A:
            self.pikmin_gen_view.MOVE_LEFT = 1
        elif event.key() == Qt.Key_D:
            self.pikmin_gen_view.MOVE_RIGHT = 1
        elif event.key() == Qt.Key_Q:
            self.pikmin_gen_view.MOVE_UP = 1
        elif event.key() == Qt.Key_E:
            self.pikmin_gen_view.MOVE_DOWN = 1

        if event.key() == Qt.Key_Plus:
            self.pikmin_gen_view.zoom_in()
        elif event.key() == Qt.Key_Minus:
            self.pikmin_gen_view.zoom_out()

    def keyReleaseEvent(self, event: QtGui.QKeyEvent):
        if event.key() == Qt.Key_Shift:
            self.pikmin_gen_view.shift_is_pressed = False
        elif event.key() == Qt.Key_R:
            self.pikmin_gen_view.rotation_is_pressed = False
        elif event.key() == Qt.Key_H:
            self.pikmin_gen_view.change_height_is_pressed = False

        if event.key() == Qt.Key_W:
            self.pikmin_gen_view.MOVE_FORWARD = 0
        elif event.key() == Qt.Key_S:
            self.pikmin_gen_view.MOVE_BACKWARD = 0
        elif event.key() == Qt.Key_A:
            self.pikmin_gen_view.MOVE_LEFT = 0
        elif event.key() == Qt.Key_D:
            self.pikmin_gen_view.MOVE_RIGHT = 0
        elif event.key() == Qt.Key_Q:
            self.pikmin_gen_view.MOVE_UP = 0
        elif event.key() == Qt.Key_E:
            self.pikmin_gen_view.MOVE_DOWN = 0

    def action_rotate_object(self, deltarotation):
        #obj.set_rotation((None, round(angle, 6), None))
        for obj in self.pikmin_gen_view.selected:
            if hasattr(obj, "rotation"):
                obj.rotation += deltarotation

        if len(self.pikmin_gen_view.selected) == 1:
            obj = self.pikmin_gen_view.selected[0]
            if hasattr(obj, "rotation"):
                self.pik_control.set_info(self.update_3d, obj, obj.position, obj.rotation)
            else:
                self.pik_control.set_info(self.update_3d, obj, obj.position, None)
            #self.pik_control.set_info(self.update_3d, obj, obj.position, obj.rotation)

        #self.pikmin_gen_view.update()
        self.pikmin_gen_view.do_redraw()
        self.set_has_unsaved_changes(True)

    def action_ground_objects(self):
        for obj in self.pikmin_gen_view.selected:
            if self.pikmin_gen_view.collision is None:
                return None
            height = self.pikmin_gen_view.collision.collide_ray_downwards(obj.position.x, obj.position.z)

            if height is not None:
                obj.position.y = height

        if len(self.pikmin_gen_view.selected) == 1:
            obj = self.pikmin_gen_view.selected[0]
            if hasattr(obj, "rotation"):
                self.pik_control.set_info(self.update_3d, obj, obj.position, obj.rotation)
            else:
                self.pik_control.set_info(self.update_3d, obj, obj.position, None)
        self.pikmin_gen_view.gizmo.move_to_average(self.pikmin_gen_view.selected)
        self.set_has_unsaved_changes(True)
        self.pikmin_gen_view.waypoints.set_dirty()
        self.pikmin_gen_view.do_redraw()

    def action_delete_objects(self):
        tobedeleted = []
        for obj in self.pikmin_gen_view.selected:
            if isinstance(obj, Waypoint):
                self.pikmin_gen_view.waypoints.paths.remove_waypoint(obj)
            else:
                self.pikmin_gen_file.generators.remove(obj)
                if obj in self.editing_windows:
                    self.editing_windows[obj].destroy()
                    del self.editing_windows[obj]

            tobedeleted.append(obj)
        self.pikmin_gen_view.selected = []

        self.pik_control.reset_info()
        self.pikmin_gen_view.gizmo.hidden = True
        #self.pikmin_gen_view.update()
        self.pikmin_gen_view.do_redraw()
        self.pikmin_gen_view.waypoints.set_paths_dirty()
        self.history.add_history_removeobjects(tobedeleted)
        self.set_has_unsaved_changes(True)

    @catch_exception
    def action_undo(self):
        res = self.history.history_undo()
        if res is None:
            return
        action, val = res

        if action == "AddObject":
            obj = val
            if isinstance(obj, Waypoint):
                self.pikmin_gen_view.waypoints.paths.remove_waypoint(obj)
            else:
                self.pikmin_gen_file.generators.remove(obj)
                if obj in self.editing_windows:
                    self.editing_windows[obj].destroy()
                    del self.editing_windows[obj]

            if len(self.pikmin_gen_view.selected) == 1 and self.pikmin_gen_view.selected[0] is obj:
                self.pik_control.reset_info()
            elif obj in self.pik_control.objectlist:
                self.pik_control.reset_info()
            if obj in self.pikmin_gen_view.selected:
                self.pikmin_gen_view.selected.remove(obj)
                self.pikmin_gen_view.gizmo.hidden = True

            #self.pikmin_gen_view.update()
            self.pikmin_gen_view.do_redraw()

        if action == "RemoveObjects":
            for obj in val:
                if isinstance(obj, Waypoint):
                    print("trying to read a removed waypoint")
                    self.pikmin_gen_view.waypoints.paths.readd_waypoint(obj)
                else:
                    self.pikmin_gen_file.generators.append(obj)

            #self.pikmin_gen_view.update()
            self.pikmin_gen_view.do_redraw()

        self.pikmin_gen_view.waypoints.set_paths_dirty()

        self.set_has_unsaved_changes(True)

    @catch_exception
    def action_redo(self):
        res = self.history.history_redo()
        if res is None:
            return

        action, val = res

        if action == "AddObject":
            obj = val
            if isinstance(obj, Waypoint):
                self.pikmin_gen_view.waypoints.paths.readd_waypoint(obj)
            else:
                self.pikmin_gen_file.generators.append(obj)

            #self.pikmin_gen_view.update()
            self.pikmin_gen_view.do_redraw()

        if action == "RemoveObjects":
            for obj in val:
                if isinstance(obj, Waypoint):
                    print("trying to remove an waypoint")
                    self.pikmin_gen_view.waypoints.paths.remove_waypoint(obj)
                else:
                    self.pikmin_gen_file.generators.remove(obj)
                    if obj in self.editing_windows:
                        self.editing_windows[obj].destroy()
                        del self.editing_windows[obj]

                if len(self.pikmin_gen_view.selected) == 1 and self.pikmin_gen_view.selected[0] is obj:
                    self.pik_control.reset_info()
                elif obj in self.pik_control.objectlist:
                    self.pik_control.reset_info()
                if obj in self.pikmin_gen_view.selected:
                    self.pikmin_gen_view.selected.remove(obj)
                    self.pikmin_gen_view.gizmo.hidden = True

            #self.pikmin_gen_view.update()
            self.pikmin_gen_view.do_redraw()
        self.pikmin_gen_view.waypoints.set_paths_dirty()
        self.set_has_unsaved_changes(True)

    def create_field_edit_action(self, fieldname):
        attribute = "lineedit_"+fieldname

        @catch_exception
        def change_field(text):
            if text == "":
                return
            try:
                #val = float(getattr(self.pik_control, attribute).text())
                val = float(text)
            except Exception as e:
                print(e)
                #open_error_dialog(str(e), self)
            else:
                if len(self.pikmin_gen_view.selected) == 1:
                    pikobject = self.pikmin_gen_view.selected[0]

                    coord = fieldname[-1]
                    if fieldname.startswith("coordinate"):
                        setattr(pikobject.position, coord, val)
                        #setattr(pikobject, coord, val)
                        #setattr(pikobject, "position_"+coord, val)
                        #setattr(pikobject, "offset_"+coord, 0)  # We reset offset to 0 for ease

                    elif fieldname.startswith("rotation"):
                        setattr(pikobject.rotation, coord, val)
                        """if pikobject.object_type == "{item}":
                            if coord == "x": pikobject.set_rotation((val, None, None))
                            elif coord == "y": pikobject.set_rotation((None, val, None))
                            elif coord == "z": pikobject.set_rotation((None, None, val))
                        elif pikobject.object_type == "{teki}" and coord == "y":
                            pikobject.set_rotation((None, val, None))
                        elif pikobject.object_type == "{pelt}":
                            if coord == "x": pikobject.set_rotation((val, None, None))
                            elif coord == "y": pikobject.set_rotation((None, val, None))
                            elif coord == "z": pikobject.set_rotation((None, None, val))"""
                    #self.pikmin_gen_view.update()
                    self.pikmin_gen_view.do_redraw()
                    if not self._justupdatingselectedobject:
                        self.set_has_unsaved_changes(True)

        return change_field

    def action_open_editwindow_shortcut(self):
        if self.pik_control.button_edit_object.isEnabled():
            self.action_open_editwindow()

    @catch_exception
    def action_open_editwindow(self):
        if self.pikmin_gen_file is not None:
            selected = self.pikmin_gen_view.selected

            if len(self.pikmin_gen_view.selected) == 1:
                currentobj = selected[0]

                if currentobj not in self.editing_windows:
                    self.editing_windows[currentobj] = PikObjectEditor()
                    self.editing_windows[currentobj].set_content(currentobj)

                    @catch_exception
                    def action_editwindow_save_data():
                        newobj = self.editing_windows[currentobj].get_content()
                        if newobj is not None:
                            currentobj.from_other(newobj)
                            self.pik_control.set_info(self.update_3d, currentobj,
                                                      currentobj.position,
                                                      currentobj.rotation)
                            #self.pikmin_gen_view.update()
                            self.pikmin_gen_view.do_redraw()

                            self.set_has_unsaved_changes(True)

                    @catch_exception
                    def action_close_edit_window():
                        #self.editing_windows[currentobj].destroy()
                        del self.editing_windows[currentobj]

                    self.editing_windows[currentobj].button_savetext.pressed.connect(action_editwindow_save_data)
                    self.editing_windows[currentobj].closing.connect(action_close_edit_window)
                    self.editing_windows[currentobj].show()

                else:
                    self.editing_windows[currentobj].activateWindow()

    def update_3d(self):
        #self.pikmin_gen_view.gizmo.move_to_average(self.level_view.selected_positions)
        self.pikmin_gen_view.waypoints.set_dirty()
        self.pikmin_gen_view.do_redraw()

    @catch_exception
    def action_update_info(self):
        if self.pikmin_gen_file is not None:
            selected = self.pikmin_gen_view.selected
            self._justupdatingselectedobject = True
            if len(self.pikmin_gen_view.selected) == 1:
                currentobj = selected[0]

                if isinstance(currentobj, Waypoint):
                    if self.pik_control.button_connect.isChecked():
                        if currentobj != self.last_waypoint:
                            hintDefault = 0 if self.loaded_paths.version == 7 else None
                            data = (100.0, 0, 0, hintDefault, hintDefault)

                            self.last_waypoint.add_path_to(currentobj, *data)
                            self.last_waypoint = currentobj
                    elif self.pik_control.button_disconnect.isChecked():
                        if currentobj != self.last_waypoint:
                            self.last_waypoint.remove_path_to(currentobj)
                            self.last_waypoint = currentobj
                    self.pikmin_gen_view.waypoints.set_paths_dirty()
                if not hasattr(currentobj, "rotation"):
                    self.pik_control.set_info(self.update_3d, currentobj,
                                              currentobj.position,
                                              None)
                else:
                    self.pik_control.set_info(self.update_3d, currentobj,
                                              currentobj.position,
                                              currentobj.rotation)

                #if currentobj.object_type == "{teki}":
                #    self.pik_control.lineedit_rotationx.setDisabled(True)
                #    self.pik_control.lineedit_rotationz.setDisabled(True)

            else:
                self.pik_control.reset_info("{0} objects selected".format(len(self.pikmin_gen_view.selected)))
                """objectnames = []
                for obj in self.pikmin_gen_view.selected:
                    if len(objectnames) >= 30:
                        break

                    objectnames.append(obj.get_useful_object_name())

                objectnames.sort()

                self.pik_control.comment_label.setText("Selected objects:\n" + (", ".join(objectnames)))"""
                self.pik_control.set_objectlist(self.pikmin_gen_view.selected)
            self._justupdatingselectedobject = False

    @catch_exception
    def mapview_showcontextmenu(self, position):
        context_menu = QMenu(self)
        action = QAction("Copy Coordinates", self)
        action.triggered.connect(self.action_copy_coords_to_clipboard)
        context_menu.addAction(action)
        context_menu.exec(self.mapToGlobal(position))
        context_menu.destroy()

    def action_copy_coords_to_clipboard(self):
        if self.current_coordinates is not None:
            QApplication.clipboard().setText(", ".join(str(x) for x in self.current_coordinates))

    def action_update_position(self, event, pos):
        self.current_coordinates = pos
        self.statusbar.showMessage(str(pos))

    def action_connect_button_pressed(self):
        print("Hey")

        self.pik_control.button_disconnect.setChecked(False)

        #self.pikmin_gen_view.gizmo.hidden = not is_checked

        if len(self.pikmin_gen_view.selected) > 0 and isinstance(self.pikmin_gen_view.selected[0], Waypoint):
            self.last_waypoint = self.pikmin_gen_view.selected[0]
        #self.pik_control.button_connect.setChecked(True)

    def action_connect_button_pressed_shortcut(self):
        if self.pik_control.button_connect.isEnabled():
            is_checked = self.pik_control.button_connect.isChecked()
            is_checked = self.pik_control.button_connect.setChecked(not is_checked)
            self.action_connect_button_pressed()

    def action_disconnect_button_pressed(self):
        if self.pik_control.button_disconnect.isEnabled():
            is_checked = self.pik_control.button_disconnect.isChecked()
            self.pik_control.button_connect.setChecked(False)

            #self.pikmin_gen_view.gizmo.hidden = not is_checked

            if len(self.pikmin_gen_view.selected) > 0 and isinstance(self.pikmin_gen_view.selected[0], Waypoint):
                self.last_waypoint = self.pikmin_gen_view.selected[0]
            #self.pik_control.button_disconnect.setChecked(not is_checked)

    def action_disconnect_button_pressed_shortcut(self):
        if self.pik_control.button_disconnect.isEnabled():
            is_checked = self.pik_control.button_disconnect.isChecked()
            is_checked = self.pik_control.button_disconnect.setChecked(not is_checked)
            self.action_disconnect_button_pressed()


class EditorHistory(object):
    def __init__(self, historysize):
        self.history = []
        self.step = 0
        self.historysize = historysize

    def reset(self):
        del self.history
        self.history = []
        self.step = 0

    def _add_history(self, entry):
        if self.step == len(self.history):
            self.history.append(entry)
            self.step += 1
        else:
            for i in range(len(self.history) - self.step):
                self.history.pop()
            self.history.append(entry)
            self.step += 1
            assert len(self.history) == self.step

        if len(self.history) > self.historysize:
            for i in range(len(self.history) - self.historysize):
                self.history.pop(0)
                self.step -= 1

    def add_history_addobject(self, pikobject):
        self._add_history(("AddObject", pikobject))

    def add_history_removeobjects(self, objects):
        self._add_history(("RemoveObjects", objects))

    def history_undo(self):
        if self.step == 0:
            return None

        self.step -= 1
        return self.history[self.step]

    def history_redo(self):
        if self.step == len(self.history):
            return None

        item = self.history[self.step]
        self.step += 1
        return item


import sys

def except_hook(cls, exception, traceback):
    sys.__excepthook__(cls, exception, traceback)



if __name__ == "__main__":
    #import sys
    import platform
    import argparse

    sys.excepthook = except_hook

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputgen", default=None,
                        help="Path to generator file to be loaded.")
    parser.add_argument("--collision", default=None,
                        help="Path to collision to be loaded.")
    parser.add_argument("--waterbox", default=None,
                        help="Path to waterbox file to be loaded.")

    args = parser.parse_args()

    app = QApplication(sys.argv)

    if platform.system() == "Windows":
        import ctypes
        myappid = 'P2GeneratorsEditor'  # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    with open("log.txt", "w") as f:
        #sys.stdout = f
        #sys.stderr = f
        print("Python version: ", sys.version)
        pikmin_gui = GenEditor()
        pikmin_gui.setWindowIcon(QtGui.QIcon('resources/icon.ico'))

        if args.inputgen is not None:
            with open(args.inputgen, "r", encoding="shift_jis-2004", errors="backslashreplace") as f:
                pikmin_gen_file = PikminGenFile()
                pikmin_gen_file.from_file(f)

            pikmin_gui.setup_gen_file(pikmin_gen_file, args.inputgen)

        pikmin_gui.show()

        if args.collision is not None:
            if args.collision.endswith(".obj"):
                with open(args.collision, "r") as f:
                    verts, faces, normals = py_obj.read_obj(f)

            elif args.collision.endswith(".bin"):
                with open(args.collision, "rb") as f:
                    collision = py_obj.PikminCollision(f)
                verts = collision.vertices
                faces = [face[0] for face in collision.faces]

            elif args.collision.endswith(".szs") or args.collision.endswith(".arc"):
                with open(args.collision, "rb") as f:
                    archive = Archive.from_file(f)
                f = archive["text/grid.bin"]
                collision = py_obj.PikminCollision(f)

                verts = collision.vertices
                faces = [face[0] for face in collision.faces]

            else:
                raise RuntimeError("Unknown collision file type:", args.collision)

            pikmin_gui.setup_collision(verts, faces, args.collision)

        if args.waterbox is not None:
            if args.waterbox.endswith(".txt"):
                with open(args.waterbox, "r", encoding="shift_jis-2004", errors="backslashreplace") as f:
                    waterboxfile = WaterboxTxt()
                    waterboxfile.from_file(f)
            elif args.waterbox.endswith(".szs") or args.waterbox.endwith(".arc"):
                with open(args.waterbox, "rb") as f:
                    archive = Archive.from_file(f)
                    # try:
                    f = archive["text/waterbox.txt"]
                    # print(f.read())
                    f.seek(0)
                    waterboxfile = WaterboxTxt()
                    waterboxfile.from_file(TextIOWrapper(f, encoding="shift_jis-2004", errors="backslashreplace"))
            else:
                raise RuntimeError("Unknown waterbox file type:", args.waterbox)

            pikmin_gui.setup_waterboxes(waterboxfile)

        err_code = app.exec()

    sys.exit(err_code)