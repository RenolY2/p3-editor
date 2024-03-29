import traceback
import os
from time import sleep
from timeit import default_timer
from io import StringIO
from math import sin, cos, atan2, radians, degrees, pi, tan

from OpenGL.GL import *
from OpenGL.GLU import *

from PyQt5.QtGui import QMouseEvent, QWheelEvent, QPainter, QColor, QFont, QFontMetrics, QPolygon, QImage, QPixmap, QKeySequence
from PyQt5.QtWidgets import (QWidget, QListWidget, QListWidgetItem, QDialog, QMenu, QLineEdit,
                            QMdiSubWindow, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QTextEdit, QAction, QShortcut)
import PyQt5.QtWidgets as QtWidgets
import PyQt5.QtCore as QtCore
from PyQt5.QtCore import QSize, pyqtSignal, QPoint, QRect
from PyQt5.QtCore import Qt


from helper_functions import calc_zoom_in_factor, calc_zoom_out_factor
from lib.libgen import GeneratorObject
from lib.collision import Collision
from widgets.editor_widgets import catch_exception, catch_exception_with_dialog
#from pikmingen import PikminObject
from libpiktxt import PikminTxt
from opengltext import draw_collision
from lib.vectors import Matrix4x4, Vector3, Line, Plane, Triangle
import pikmingen
from lib.model_rendering import TexturedPlane, Model, Grid, GenericObject
from gizmo import Gizmo
from lib.object_models import ObjectModels, WaypointsGraphics
from editor_controls import UserControl
from lib.libpath import Paths, Waypoint
import numpy

MOUSE_MODE_NONE = 0
MOUSE_MODE_MOVEWP = 1
MOUSE_MODE_ADDWP = 2
MOUSE_MODE_CONNECTWP = 3

MODE_TOPDOWN = 0
MODE_3D = 1


class SelectionQueue(list):
    def __init__(self):
        super().__init__()

    def queue_selection(self, x, y, width, height, shift_pressed, do_gizmo=False):
        if do_gizmo:
            for i in self:
                if i[-1] is True:
                    return
        self.append((x, y, width, height, shift_pressed, do_gizmo))

    def clear(self):
        tmp = [x for x in self]
        for val in tmp:
            if tmp[-1] is True:
                self.remove(tmp)

    def queue_pop(self):
        if len(self) > 0:
            return self.pop(0)

        else:
            return None


class GenMapViewer(QtWidgets.QOpenGLWidget):
    mouse_clicked = pyqtSignal(QMouseEvent)
    entity_clicked = pyqtSignal(QMouseEvent, str)
    mouse_dragged = pyqtSignal(QMouseEvent)
    mouse_released = pyqtSignal(QMouseEvent)
    mouse_wheel = pyqtSignal(QWheelEvent)
    position_update = pyqtSignal(QMouseEvent, tuple)
    height_update = pyqtSignal(float)
    select_update = pyqtSignal()
    move_points = pyqtSignal(float, float, float)
    connect_update = pyqtSignal(int, int)
    create_waypoint = pyqtSignal(float, float)
    create_waypoint_3d = pyqtSignal(float, float, float)

    rotate_current = pyqtSignal(Vector3)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._zoom_factor = 10
        self.setFocusPolicy(Qt.ClickFocus)

        self.SIZEX = 1024#768#1024
        self.SIZEY = 1024#768#1024

        self.canvas_width, self.canvas_height = self.width(), self.height()

        #self.setMinimumSize(QSize(self.SIZEX, self.SIZEY))
        #self.setMaximumSize(QSize(self.SIZEX, self.SIZEY))
        self.setObjectName("bw_map_screen")

        self.origin_x = self.SIZEX//2
        self.origin_z = self.SIZEY//2

        self.offset_x = 0
        self.offset_z = 0

        self.left_button_down = False
        self.mid_button_down = False
        self.right_button_down = False
        self.drag_last_pos = None

        self.selected = []

        self.selectionbox_start = None
        self.selectionbox_end = None

        self.visualize_cursor = None

        self.click_mode = 0

        self.level_image = None

        self.collision = None

        self.highlighttriangle = None

        self.setMouseTracking(True)

        self.pikmin_generators = None

        self.mousemode = MOUSE_MODE_NONE

        self.overlapping_wp_index = 0
        self.editorconfig = None

        #self.setContextMenuPolicy(Qt.CustomContextMenu)

        self.spawnpoint = None

        self.shift_is_pressed = False
        self.rotation_is_pressed = False
        self.last_drag_update = 0
        self.change_height_is_pressed = False
        self.last_mouse_move = None

        self.timer = QtCore.QTimer()
        self.timer.setInterval(2)
        self.timer.timeout.connect(self.render_loop)
        self.timer.start()
        self._lastrendertime = 0
        self._lasttime = 0

        self._frame_invalid = False

        self.MOVE_UP = 0
        self.MOVE_DOWN = 0
        self.MOVE_LEFT = 0
        self.MOVE_RIGHT = 0
        self.MOVE_FORWARD = 0
        self.MOVE_BACKWARD = 0
        self.SPEEDUP = 0

        self._wasdscrolling_speed = 1
        self._wasdscrolling_speedupfactor = 3

        self.main_model = None
        self.buffered_deltas = []

        # 3D Setup
        self.mode = MODE_TOPDOWN
        self.camera_horiz = pi*(1/2)
        self.camera_vertical = -pi*(1/4)
        self.camera_height = 1000
        self.last_move = None

        #self.selection_queue = []
        self.selectionqueue = SelectionQueue()

        self.selectionbox_projected_start = None
        self.selectionbox_projected_end = None

        #self.selectionbox_projected_2d = None
        self.selectionbox_projected_origin = None
        self.selectionbox_projected_up = None
        self.selectionbox_projected_right = None
        self.selectionbox_projected_coords = None
        self.last_position_update = 0
        self.move_collision_plane = Plane(Vector3(0.0, 0.0, 0.0), Vector3(1.0, 0.0, 0.0), Vector3(0.0, 1.0, 0.0))

        self.paths = Paths()
        self.usercontrol = UserControl(self)

        # Initialize some models
        with open("resources/gizmo.obj", "r") as f:
            self.gizmo = Gizmo.from_obj(f, rotate=True)

        #self.generic_object = GenericObject()
        self.models = ObjectModels()
        self.grid = Grid(10000, 10000)
        self.waypoints = WaypointsGraphics()

        self.modelviewmatrix = None
        self.projectionmatrix = None

    @catch_exception_with_dialog
    def initializeGL(self):
        print(self.context(), self.isValid())
        self.makeCurrent()
        print("OpenGL Version: ", glGetString(GL_VERSION))
        self.rotation_visualizer = glGenLists(1)
        glNewList(self.rotation_visualizer, GL_COMPILE)
        glColor4f(0.0, 0.0, 1.0, 1.0)
        glLineWidth(2.0)
        glBegin(GL_LINES)
        glVertex3f(0.0, 0.0, 0.0)
        glVertex3f(0.0, 40.0, 0.0)
        glEnd()
        glEndList()

        self.models.init_gl()

    def resizeGL(self, width, height):
        # Called upon window resizing: reinitialize the viewport.
        # update the window size
        self.canvas_width, self.canvas_height = width, height
        # paint within the whole window
        glEnable(GL_DEPTH_TEST)
        glViewport(0, 0, self.canvas_width, self.canvas_height)

    @catch_exception
    def set_editorconfig(self, config):
        self.editorconfig = config
        self._wasdscrolling_speed = config.getfloat("wasdscrolling_speed")
        self._wasdscrolling_speedupfactor = config.getfloat("wasdscrolling_speedupfactor")

    def change_from_topdown_to_3d(self):
        if self.mode == MODE_3D:
            return
        else:
            self.mode = MODE_3D

            if self.mousemode == MOUSE_MODE_NONE:
                self.setContextMenuPolicy(Qt.DefaultContextMenu)

            # This is necessary so that the position of the 3d camera equals the middle of the topdown view
            self.offset_x *= -1
            self.do_redraw()

    def change_from_3d_to_topdown(self):
        if self.mode == MODE_TOPDOWN:
            return
        else:
            self.mode = MODE_TOPDOWN
            if self.mousemode == MOUSE_MODE_NONE:
                self.setContextMenuPolicy(Qt.CustomContextMenu)

            self.offset_x *= -1
            self.do_redraw()

    @catch_exception
    def render_loop(self):
        now = default_timer()

        diff = now-self._lastrendertime
        timedelta = now-self._lasttime

        if self.mode == MODE_TOPDOWN:
            self.handle_arrowkey_scroll(timedelta)
        else:
            self.handle_arrowkey_scroll_3d(timedelta)

        if diff > 1 / 60.0:
            if self._frame_invalid:
                self.update()
                self._lastrendertime = now
                self._frame_invalid = False
        self._lasttime = now

    def handle_arrowkey_scroll(self, timedelta):
        if self.selectionbox_projected_coords is not None:
            return

        diff_x = diff_y = 0
        #print(self.MOVE_UP, self.MOVE_DOWN, self.MOVE_LEFT, self.MOVE_RIGHT)
        speedup = 1

        if self.shift_is_pressed:
            speedup = self._wasdscrolling_speedupfactor

        if self.MOVE_FORWARD == 1 and self.MOVE_BACKWARD == 1:
            diff_y = 0
        elif self.MOVE_FORWARD == 1:
            diff_y = 1*speedup*self._wasdscrolling_speed*timedelta
        elif self.MOVE_BACKWARD == 1:
            diff_y = -1*speedup*self._wasdscrolling_speed*timedelta

        if self.MOVE_LEFT == 1 and self.MOVE_RIGHT == 1:
            diff_x = 0
        elif self.MOVE_LEFT == 1:
            diff_x = 1*speedup*self._wasdscrolling_speed*timedelta
        elif self.MOVE_RIGHT == 1:
            diff_x = -1*speedup*self._wasdscrolling_speed*timedelta

        if diff_x != 0 or diff_y != 0:
            if self.zoom_factor > 1.0:
                self.offset_x += diff_x * (1.0 + (self.zoom_factor - 1.0) / 2.0)
                self.offset_z += diff_y * (1.0 + (self.zoom_factor - 1.0) / 2.0)
            else:
                self.offset_x += diff_x
                self.offset_z += diff_y
            # self.update()

            self.do_redraw()

    def handle_arrowkey_scroll_3d(self, timedelta):
        if self.selectionbox_projected_coords is not None:
            return

        diff_x = diff_y = diff_height = 0
        #print(self.MOVE_UP, self.MOVE_DOWN, self.MOVE_LEFT, self.MOVE_RIGHT)
        speedup = 1

        forward_vec = Vector3(cos(self.camera_horiz), sin(self.camera_horiz), 0)
        sideways_vec = Vector3(sin(self.camera_horiz), -cos(self.camera_horiz), 0)

        if self.shift_is_pressed:
            speedup = self._wasdscrolling_speedupfactor

        if self.MOVE_FORWARD == 1 and self.MOVE_BACKWARD == 1:
            forward_move = forward_vec*0
        elif self.MOVE_FORWARD == 1:
            forward_move = forward_vec*(1*speedup*self._wasdscrolling_speed*timedelta)
        elif self.MOVE_BACKWARD == 1:
            forward_move = forward_vec*(-1*speedup*self._wasdscrolling_speed*timedelta)
        else:
            forward_move = forward_vec*0

        if self.MOVE_LEFT == 1 and self.MOVE_RIGHT == 1:
            sideways_move = sideways_vec*0
        elif self.MOVE_LEFT == 1:
            sideways_move = sideways_vec*(-1*speedup*self._wasdscrolling_speed*timedelta)
        elif self.MOVE_RIGHT == 1:
            sideways_move = sideways_vec*(1*speedup*self._wasdscrolling_speed*timedelta)
        else:
            sideways_move = sideways_vec*0

        if self.MOVE_UP == 1 and self.MOVE_DOWN == 1:
            diff_height = 0
        elif self.MOVE_UP == 1:
            diff_height = 1*speedup*self._wasdscrolling_speed*timedelta
        elif self.MOVE_DOWN == 1:
            diff_height = -1 * speedup * self._wasdscrolling_speed * timedelta

        if not forward_move.is_zero() or not sideways_move.is_zero() or diff_height != 0:
            #if self.zoom_factor > 1.0:
            #    self.offset_x += diff_x * (1.0 + (self.zoom_factor - 1.0) / 2.0)
            #    self.offset_z += diff_y * (1.0 + (self.zoom_factor - 1.0) / 2.0)
            #else:
            self.offset_x += (forward_move.x + sideways_move.x)
            self.offset_z += (forward_move.y + sideways_move.y)
            self.camera_height += diff_height
            # self.update()

            self.do_redraw()

    def set_arrowkey_movement(self, up, down, left, right):
        self.MOVE_UP = up
        self.MOVE_DOWN = down
        self.MOVE_LEFT = left
        self.MOVE_RIGHT = right

    def do_redraw(self, force=False):
        self._frame_invalid = True
        if force:
            self._lastrendertime = 0
            self.update()

    def reset(self, keep_collision=False):
        self.overlapping_wp_index = 0
        self.shift_is_pressed = False
        self.SIZEX = 1024
        self.SIZEY = 1024
        self.origin_x = self.SIZEX//2
        self.origin_z = self.SIZEY//2
        self.last_drag_update = 0

        self.left_button_down = False
        self.mid_button_down = False
        self.right_button_down = False
        self.drag_last_pos = None

        self.selectionbox_start = None
        self.selectionbox_end = None

        self.selected = []

        if not keep_collision:
            # Potentially: Clear collision object too?
            self.level_image = None
            self.offset_x = 0
            self.offset_z = 0
            self._zoom_factor = 10
            #self.waterboxes = []

        self.pikmin_generators = None

        self.mousemode = MOUSE_MODE_NONE
        self.spawnpoint = None
        self.rotation_is_pressed = False

        self._frame_invalid = False

        self.MOVE_UP = 0
        self.MOVE_DOWN = 0
        self.MOVE_LEFT = 0
        self.MOVE_RIGHT = 0
        self.SPEEDUP = 0

    def set_collision(self, verts, faces):
        self.collision = Collision(verts, faces)

        if self.main_model is None:
            self.main_model = glGenLists(1)

        glNewList(self.main_model, GL_COMPILE)
        #glBegin(GL_TRIANGLES)
        draw_collision(verts, faces)
        #glEnd()
        glEndList()

    def set_mouse_mode(self, mode):
        assert mode in (MOUSE_MODE_NONE, MOUSE_MODE_ADDWP, MOUSE_MODE_CONNECTWP, MOUSE_MODE_MOVEWP)

        self.mousemode = mode

        if self.mousemode == MOUSE_MODE_NONE and self.mode == MODE_TOPDOWN:
            self.setContextMenuPolicy(Qt.CustomContextMenu)
        else:
            self.setContextMenuPolicy(Qt.DefaultContextMenu)

    @property
    def zoom_factor(self):
        return self._zoom_factor/10.0

    def zoom(self, fac):
        if 0.1 < (self.zoom_factor + fac) <= 25:
            self._zoom_factor += int(fac*10)
            #self.update()
            self.do_redraw()

    def mouse_coord_to_world_coord(self, mouse_x, mouse_y):
        zf = self.zoom_factor
        width, height = self.canvas_width, self.canvas_height
        camera_width = width * zf
        camera_height = height * zf

        topleft_x = -camera_width / 2 - self.offset_x
        topleft_y = camera_height / 2 + self.offset_z

        relx = mouse_x / width
        rely = mouse_y / height
        res = (topleft_x + relx*camera_width, topleft_y - rely*camera_height)

        return res

    def mouse_coord_to_world_coord_transform(self, mouse_x, mouse_y):
        mat4x4 = Matrix4x4.from_opengl_matrix(*glGetFloatv(GL_PROJECTION_MATRIX))
        width, height = self.canvas_width, self.canvas_height
        result = mat4x4.multiply_vec4(mouse_x-width/2, mouse_y-height/2, 0, 1)

        return result

    #@catch_exception_with_dialog
    #@catch_exception
    def paintGL(self):
        start = default_timer()
        offset_x = self.offset_x
        offset_z = self.offset_z

        #start = default_timer()
        glClearColor(1.0, 1.0, 1.0, 0.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        width, height = self.canvas_width, self.canvas_height

        if self.mode == MODE_TOPDOWN:
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            zf = self.zoom_factor
            #glOrtho(-6000.0, 6000.0, -6000.0, 6000.0, -3000.0, 2000.0)
            camera_width = width*zf
            camera_height = height*zf

            glOrtho(-camera_width / 2 - offset_x, camera_width / 2 - offset_x,
                    -camera_height / 2 + offset_z, camera_height / 2 + offset_z, -3000.0, 2000.0)

            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()
        else:
            #glEnable(GL_CULL_FACE)
            # set yellow color for subsequent drawing rendering calls

            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(75, width / height, 3.0, 12800.0*1.5)

            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()

            look_direction = Vector3(cos(self.camera_horiz), sin(self.camera_horiz), sin(self.camera_vertical))
            # look_direction.unify()
            fac = 1.01 - abs(look_direction.z)
            # print(fac, look_direction.z, look_direction)

            gluLookAt(self.offset_x, self.offset_z, self.camera_height,
                      self.offset_x + look_direction.x * fac, self.offset_z + look_direction.y * fac,
                      self.camera_height + look_direction.z,
                      0, 0, 1)

            self.camera_direction = Vector3(look_direction.x * fac, look_direction.y * fac, look_direction.z)

            #print(self.camera_direction)

        self.modelviewmatrix = numpy.transpose(numpy.reshape(glGetFloatv(GL_MODELVIEW_MATRIX), (4,4)))
        self.projectionmatrix = numpy.transpose(numpy.reshape(glGetFloatv(GL_PROJECTION_MATRIX), (4,4)))
        self.mvp_mat = numpy.dot(self.projectionmatrix, self.modelviewmatrix)
        self.modelviewmatrix_inv = numpy.linalg.inv(self.modelviewmatrix)

        campos = Vector3(self.offset_x, self.camera_height, -self.offset_z)
        self.campos = campos

        if self.mode == MODE_TOPDOWN:
            gizmo_scale = 3*zf
        else:

            gizmo_scale = (self.gizmo.position - campos).norm() / 130.0


        self.gizmo_scale = gizmo_scale

        #print(self.gizmo.position, campos)
        do_rotation = False
        for selected in self.selected:
            if not isinstance(selected, Waypoint):
                do_rotation = True

        while len(self.selectionqueue) > 0:
            glClearColor(1.0, 1.0, 1.0, 0.0)
            #
            click_x, click_y, clickwidth, clickheight, shiftpressed, do_gizmo = self.selectionqueue.queue_pop()
            click_y = height - click_y
            hit = 0xFF

            #print("received request", do_gizmo)

            if clickwidth == 1 and clickheight == 1:
                self.gizmo.render_collision_check(gizmo_scale, is3d=self.mode == MODE_3D, rotation=do_rotation)
                pixels = glReadPixels(click_x, click_y, clickwidth, clickheight, GL_RGB, GL_UNSIGNED_BYTE)
                #print(pixels)
                hit = pixels[2]
                if do_gizmo and hit != 0xFF:
                    self.gizmo.run_callback(hit)
                    self.gizmo.was_hit_at_all = True
                #if hit != 0xFF and do_:


            glClearColor(1.0, 1.0, 1.0, 0.0)

            if self.pikmin_generators is not None and hit == 0xFF and not do_gizmo:
                objects = self.pikmin_generators.generators
                glDisable(GL_TEXTURE_2D)
                for i, pikminobject in enumerate(objects):
                    self.models.render_object_coloredid(pikminobject, i*2)

                for i, waypoint in enumerate(self.waypoints.paths.waypoints):
                    self.models.render_waypoint_coloredid(waypoint, i*2+1)

                pixels = glReadPixels(click_x, click_y, clickwidth, clickheight, GL_RGB, GL_UNSIGNED_BYTE)
                #print(pixels, click_x, click_y, clickwidth, clickheight)
                selected = {}
                #for i in range(0, clickwidth*clickheight, 4):
                start = default_timer()
                """for x in range(0, clickwidth, 3):
                    for y in range(0, clickheight, 3):
                        i = (x + y*clickwidth)*3
                        # | (pixels[i*3+0] << 16)
                        if pixels[i + 1] != 0xFF:
                            index = (pixels[i + 1] << 8) | pixels[i + 2]
                            #print(index)
                            pikminobject = objects[index]
                            selected[pikminobject] = True
                """
                for i in range(0, clickwidth*clickheight, 13):
                        # | (pixels[i*3+0] << 16)
                        if pixels[i*3 + 1] != 0xFF:
                            index = (pixels[i*3 + 1] << 8) | pixels[i*3 + 2]
                            #print(index)
                            if index & 1:
                                obj = self.waypoints.paths.waypoints[(index-1)//2]
                            else:
                                obj = objects[index//2]

                            selected[obj] = True
                #print("select time taken", default_timer() - start)
                selected = list(selected.keys())

                #print("result:", selected)
                if not shiftpressed:
                    self.selected = selected
                    self.select_update.emit()

                elif shiftpressed:
                    for obj in selected:
                        if obj not in self.selected:
                            self.selected.append(obj)
                    self.select_update.emit()

                self.gizmo.move_to_average(self.selected)

                if len(selected) == 0:
                    #print("Select did register")
                    self.gizmo.hidden = True
                if self.mode == MODE_3D: # In case of 3D mode we need to update scale due to changed gizmo position
                    gizmo_scale = (self.gizmo.position - campos).norm() / 130.0
                #print("total time taken", default_timer() - start)
        #print("gizmo status", self.gizmo.was_hit_at_all)
        glClearColor(1.0, 1.0, 1.0, 0.0)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glEnable(GL_DEPTH_TEST)
        glDisable(GL_TEXTURE_2D)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        if self.main_model is not None:
            glCallList(self.main_model)

        glColor4f(1.0, 1.0, 1.0, 1.0)
        self.grid.render()
        if self.mode == MODE_TOPDOWN:
            glClear(GL_DEPTH_BUFFER_BIT)
        #    glDisable(GL_DEPTH_TEST)


        glEnable(GL_ALPHA_TEST)
        glAlphaFunc(GL_GEQUAL, 0.5)
        selected = self.selected
        if self.pikmin_generators is not None:

            objects = self.pikmin_generators.generators

            for pikminobject in objects:
                self.models.render_object(pikminobject, pikminobject in selected)

        glDisable(GL_TEXTURE_2D)

        for waypoint in self.waypoints.paths.waypoints:
            self.models.render_waypoint(waypoint, waypoint in selected)
        self.waypoints.render(self.models)
        """glColor4f(0.0, 1.0, 0.0, 1.0)
        rendered = {}
        for p1, p2 in self.paths.unique_paths:
            #p1 = self.paths.waypoints[p1i]
            #p2 = self.paths.waypoints[p2i]

            glBegin(GL_LINES)
            glVertex3f(p1.position.x, -p1.position.z, p1.position.y+5)
            glVertex3f(p2.position.x, -p2.position.z, p2.position.y+5)
            glEnd()

            if p1 not in rendered:
                self.models.draw_sphere(p1.position, p1.radius/2)
                rendered[p1] = True
            if p2 not in rendered:
                self.models.draw_sphere(p2.position, p2.radius/2)
                rendered[p2] = True"""
        glColor4f(0.0, 1.0, 1.0, 1.0)
        """for points in self.paths.wide_paths:
            glBegin(GL_LINE_LOOP)
            for p in points:
                glVertex3f(p.x, -p.z, p.y + 5)

            glEnd()"""
        glDisable(GL_ALPHA_TEST)
        glDisable(GL_TEXTURE_2D)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)

        if self.pikmin_generators is not None:
            selected = self.selected
            objects = self.pikmin_generators.generators

            for pikminobject in objects:
                if pikminobject.name == "WaterBox":
                    scale = float(pikminobject.unknown_params["mScale"][0])
                    depth = float(pikminobject.unknown_params["mDepth"][0])
                    self.models.draw_waterbox(pikminobject.position, pikminobject.rotation.y,
                                              scale * 100, scale * 100, depth,
                                              pikminobject in selected)

        self.gizmo.render_scaled(gizmo_scale, is3d=self.mode == MODE_3D, rotation=do_rotation)



        glDisable(GL_DEPTH_TEST)
        if self.selectionbox_start is not None and self.selectionbox_end is not None:
            #print("drawing box")
            startx, startz = self.selectionbox_start
            endx, endz = self.selectionbox_end
            glColor4f(1.0, 0.0, 0.0, 1.0)
            glLineWidth(2.0)
            glBegin(GL_LINE_LOOP)
            glVertex3f(startx, startz, 0)
            glVertex3f(startx, endz, 0)
            glVertex3f(endx, endz, 0)
            glVertex3f(endx, startz, 0)

            glEnd()

        if self.selectionbox_projected_origin is not None and self.selectionbox_projected_coords is not None:
            #print("drawing box")
            origin = self.selectionbox_projected_origin
            point2, point3, point4 = self.selectionbox_projected_coords
            glColor4f(1.0, 0.0, 0.0, 1.0)
            glLineWidth(2.0)

            point1 = origin

            glBegin(GL_LINE_LOOP)
            glVertex3f(point1.x, point1.y, point1.z)
            glVertex3f(point2.x, point2.y, point2.z)
            glVertex3f(point3.x, point3.y, point3.z)
            glVertex3f(point4.x, point4.y, point4.z)
            glEnd()

        glEnable(GL_DEPTH_TEST)
        glFinish()
        now = default_timer() - start
        #print("Frame time:", now, 1/now, "fps")

    @catch_exception
    def mousePressEvent(self, event):
        self.usercontrol.handle_press(event)

    @catch_exception
    def mouseMoveEvent(self, event):
        self.usercontrol.handle_move(event)

    @catch_exception
    def mouseReleaseEvent(self, event):
        self.usercontrol.handle_release(event)

    def wheelEvent(self, event):
        wheel_delta = event.angleDelta().y()

        if self.editorconfig is not None:
            invert = self.editorconfig.getboolean("invertzoom")
            if invert:
                wheel_delta = -1*wheel_delta

        if wheel_delta < 0:
            self.zoom_out()

        elif wheel_delta > 0:
            self.zoom_in()

    def zoom_in(self):
        current = self.zoom_factor

        fac = calc_zoom_out_factor(current)

        self.zoom(fac)

    def zoom_out(self):
        current = self.zoom_factor
        fac = calc_zoom_in_factor(current)

        self.zoom(fac)

    def create_ray_from_mouseclick(self, mousex, mousey, yisup=False):
        self.camera_direction.normalize()
        height = self.canvas_height
        width = self.canvas_width

        view = self.camera_direction.copy()

        h = view.cross(Vector3(0, 0, 1))
        v = h.cross(view)

        h.normalize()
        v.normalize()

        rad = 75 * pi / 180.0
        vLength = tan(rad / 2) * 1.0
        hLength = vLength * (width / height)

        v *= vLength
        h *= hLength

        x = mousex - width / 2
        y = height - mousey- height / 2

        x /= (width / 2)
        y /= (height / 2)
        camerapos = Vector3(self.offset_x, self.offset_z, self.camera_height)

        pos = camerapos + view * 1.0 + h * x + v * y
        dir = pos - camerapos

        if yisup:
            tmp = pos.y
            pos.y = -pos.z
            pos.z = tmp

            tmp = dir.y
            dir.y = -dir.z
            dir.z = tmp

        return Line(pos, dir)

