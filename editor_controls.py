from math import pi, tan, atan2, degrees
from timeit import default_timer
import abc

from PyQt5.QtCore import Qt
from lib.vectors import Vector3, Plane, Vector2
from gizmo import AXIS_X, AXIS_Y, AXIS_Z

MOUSE_MODE_NONE = 0
MOUSE_MODE_MOVEWP = 1
MOUSE_MODE_ADDWP = 2
MOUSE_MODE_CONNECTWP = 3

MODE_TOPDOWN = 0
MODE_3D = 1


key_enums = {
    "Middle": Qt.MiddleButton,
    "Left": Qt.LeftButton,
    "Right": Qt.RightButton
}


class Buttons(object):
    def __init__(self):
        self._buttons = {}
        for key in key_enums:
            self._buttons[key] = False

    def update_status(self, event):
        for key in key_enums:
            self._buttons = event.buttons() & key_enums[key]

    def just_pressed(self, event, key):
        return not self._buttons[key] and self.is_held(event, key)

    def is_held(self, event, key):
        self._buttons[key] = event.buttons() & key_enums[key]
        return self._buttons[key]

    def just_released(self, event, key):
        return self._buttons[key] and not self.is_held(event, key)


class MouseAction(object):
    def __init__(self, name):
        self.name = name

    def condition(self, editor, buttons, event):
        return True


class ClickAction(MouseAction):
    def __init__(self, name, key):
        super().__init__(name)
        self.key = key
        assert key in key_enums

    def condition(self, editor, buttons, event):
        return True

    def just_clicked(self, editor, buttons, event):
        pass

    def move(self, editor, buttons, event):
        pass

    def just_released(self, editor, buttons, event):
        pass


class ClickDragAction(MouseAction):
    def __init__(self, name, key):
        super().__init__(name)
        self.key = key
        assert key in key_enums

        self.first_click = None

    def just_clicked(self, editor, buttons, event):
        self.first_click = Vector2(event.x(), event.y())

    def move(self, editor, buttons, event):

        pass

    def just_released(self, editor, buttons, event):
        self.first_click = None


class TopdownScroll(ClickDragAction):
    def move(self, editor, buttons, event):
        x, y = event.x(), event.y()
        d_x, d_y = event.x() - self.first_click.x, event.y() - self.first_click.y

        if editor.zoom_factor > 1.0:
            adjusted_dx = d_x * editor.zoom_factor  # (1.0 + (self.zoom_factor - 1.0))
            adjusted_dz = d_y * editor.zoom_factor  # (1.0 + (self.zoom_factor - 1.0))
        else:
            adjusted_dx = d_x
            adjusted_dz = d_y

        editor.offset_x += adjusted_dx
        editor.offset_z += adjusted_dz
        editor.do_redraw()
        self.first_click.x = event.x()
        self.first_click.y = event.y()


class TopdownSelect(ClickDragAction):
    def condition(self, editor, buttons, event):
        return (editor.gizmo.was_hit_at_all is not True) and editor.mousemode == MOUSE_MODE_NONE

    def just_clicked(self, editor, buttons, event):
        super().just_clicked(editor, buttons, event)
        x, y = self.first_click.x, self.first_click.y

        selectstartx, selectstartz = editor.mouse_coord_to_world_coord(x, y)

        editor.selectionbox_start = (selectstartx, selectstartz)

        if editor.pikmin_generators is not None:
            editor.selectionqueue.queue_selection(x, y, 1, 1,
                                           editor.shift_is_pressed)
            editor.do_redraw()

    def move(self, editor, buttons, event):
        selectendx, selectendz = editor.mouse_coord_to_world_coord(event.x(), event.y())
        editor.selectionbox_end = (selectendx, selectendz)
        editor.do_redraw()

    def just_released(self, editor, buttons, event):
        selectstartx, selectstartz = self.first_click.x, self.first_click.y
        selectendx, selectendz = event.x(), event.y()

        startx = min(selectstartx, selectendx)
        endx = max(selectstartx, selectendx)
        startz = min(selectstartz, selectendz)
        endz = max(selectstartz, selectendz)

        editor.selectionqueue.queue_selection(int(startx), int(endz), int(endx - startx) + 1, int(endz - startz) + 1,
                                       editor.shift_is_pressed)

        editor.do_redraw()

        editor.selectionbox_start = editor.selectionbox_end = None
        editor.do_redraw()


class Gizmo2DMoveX(ClickDragAction):
    def just_clicked(self, editor, buttons, event):
        super().just_clicked(editor, buttons, event)
        editor.selectionqueue.queue_selection(event.x(), event.y(), 1, 1,
                                              editor.shift_is_pressed, do_gizmo=True)
        editor.do_redraw()

    def move(self, editor, buttons, event):
        if editor.gizmo.was_hit["gizmo_x"]:
            editor.gizmo.hidden = True
            editor.gizmo.set_render_axis(AXIS_X)
            delta_x = event.x() - self.first_click.x
            self.first_click = Vector2(event.x(), event.y())
            editor.move_points.emit(delta_x*editor.zoom_factor, 0)

    def just_released(self, editor, buttons, event):
        super().just_released(editor, buttons, event)
        editor.gizmo.hidden = False
        editor.gizmo.reset_axis()
        editor.gizmo.move_to_average(editor.selected)


class Gizmo2DMoveZ(Gizmo2DMoveX):
    def move(self, editor, buttons, event):
        if editor.gizmo.was_hit["gizmo_z"]:
            editor.gizmo.hidden = True
            editor.gizmo.set_render_axis(AXIS_Z)
            delta_z = event.y() - self.first_click.y
            self.first_click = Vector2(event.x(), event.y())
            editor.move_points.emit(0, delta_z*editor.zoom_factor)


class Gizmo2DRotateY(Gizmo2DMoveX):
    def just_clicked(self, editor, buttons, event):
        super().just_clicked(editor, buttons, event)

    def move(self, editor, buttons, event):
        if editor.gizmo.was_hit["rotation_y"]:
            editor.gizmo.hidden = True
            #editor.gizmo.set_render_axis(AXIS_Z)

            x, y = editor.mouse_coord_to_world_coord(self.first_click.x, self.first_click.y)
            angle_start = atan2(-(y + editor.gizmo.position.z), x - editor.gizmo.position.x)

            x, y = editor.mouse_coord_to_world_coord(event.x(), event.y())
            angle = atan2(-(y + editor.gizmo.position.z), x - editor.gizmo.position.x)
            delta = angle_start - angle


            editor.rotate_current.emit(Vector3(0, degrees(delta), 0))

            self.first_click = Vector2(event.x(), event.y())

    def just_released(self, editor, buttons, event):
        super().just_released(editor, buttons, event)
        editor.gizmo.hidden = False
        editor.gizmo.reset_axis()
        #editor.gizmo.move_to_average(editor.selected)


class AddObjectTopDown(ClickAction):
    def condition(self, editor, buttons, event):
        return editor.mousemode == MOUSE_MODE_ADDWP

    def just_clicked(self, editor, buttons, event):
        mouse_x, mouse_z = (event.x(), event.y())
        destx, destz = editor.mouse_coord_to_world_coord(mouse_x, mouse_z)

        editor.create_waypoint.emit(destx, -destz)


class RotateCamera3D(ClickDragAction):
    pass


class UserControl(object):
    def __init__(self, editor_widget):
        self._editor_widget = editor_widget

        self.shift_pressed = False

        self.buttons = Buttons()

        self.clickdragactions = {"Left": [], "Right": [], "Middle": []}
        self.clickdragactions3d = {"Left": [], "Right": [], "Middle": []}

        self.add_action(TopdownScroll("2DScroll", "Middle"))
        self.add_action(TopdownSelect("2DSelect", "Left"))
        self.add_action(Gizmo2DMoveX("Gizmo2DMoveX", "Left"))
        self.add_action(Gizmo2DMoveZ("Gizmo2DMoveZ", "Left"))
        self.add_action(Gizmo2DRotateY("Gizmo2DRotateY", "Left"))
        self.add_action(AddObjectTopDown("AddObject2D", "Left"))


        self.last_position_update = 0.0

    def add_action(self, action):
        self.clickdragactions[action.key].append(action)

    def handle_press(self, event):
        editor = self._editor_widget

        if editor.mode == MODE_TOPDOWN:
            self.handle_press_topdown(event)
        else:
            self.handle_press_3d(event)

    def handle_release(self, event):
        editor = self._editor_widget
        if editor.mode == MODE_TOPDOWN:
            self.handle_release_topdown(event)
        else:
            self.handle_release_3d(event)

        editor.gizmo.reset_hit_status()
        editor.do_redraw()

    def handle_move(self, event):
        editor = self._editor_widget
        if editor.mode == MODE_TOPDOWN:
            self.handle_move_topdown(event)

            if default_timer() - self.last_position_update > 0.1:  # True:  # self.highlighttriangle is not None:
                mapx, mapz = editor.mouse_coord_to_world_coord(event.x(), event.y())
                self.last_position_update = default_timer()

                if editor.collision is not None:
                    height = editor.collision.collide_ray_downwards(mapx, -mapz)

                    if height is not None:
                        # self.highlighttriangle = res[1:]
                        # self.update()
                        editor.position_update.emit(event, (round(mapx, 2), round(height, 2), round(-mapz, 2)))
                    else:
                        editor.position_update.emit(event, (round(mapx, 2), None, round(-mapz, 2)))
                else:
                    editor.position_update.emit(event, (round(mapx, 2), None, round(-mapz, 2)))
        else:
            self.handle_move_3d(event)

    def handle_press_topdown(self, event):
        editor = self._editor_widget

        for key in key_enums.keys():
            if self.buttons.just_pressed(event, key):
                for action in self.clickdragactions[key]:
                    if action.condition(editor, self.buttons, event):
                        action.just_clicked(editor, self.buttons, event)

    def handle_release_topdown(self, event):
        editor = self._editor_widget

        for key in key_enums.keys():
            if self.buttons.just_released(event, key):
                for action in self.clickdragactions[key]:
                    if action.condition(editor, self.buttons, event):
                        action.just_released(editor, self.buttons, event)

    def handle_move_topdown(self, event):
        editor = self._editor_widget

        for key in key_enums.keys():
            if self.buttons.is_held(event, key):
                for action in self.clickdragactions[key]:
                    if action.condition(editor, self.buttons, event):
                        action.move(editor, self.buttons, event)
        return

    def handle_press_3d(self, event):
        editor = self._editor_widget

        for key in key_enums.keys():
            if self.buttons.just_pressed(event, key):
                for action in self.clickdragactions3d[key]:
                    if action.condition(editor, self.buttons, event):
                        action.just_clicked(editor, self.buttons, event)

        return
        if self.buttons.just_pressed(event, "Right"):
            # Disallow moving camera while doing selection
            if not (self.buttons.is_held(event, "Left") and editor.mousemode == MOUSE_MODE_NONE):
                editor.last_move = (event.x(), event.y())

        if self.buttons.just_pressed(event, "Left"):
            # Do selection
            if editor.mousemode == MOUSE_MODE_NONE and not self.buttons.is_held(event, "Right"):
                editor.selection_queue.append((event.x(), event.y(), 1, 1,
                                               editor.shift_is_pressed))
                editor.do_redraw()
                editor.selectionbox_projected_2d = (event.x(), event.y())

                editor.camera_direction.normalize()

                ray = editor.create_ray_from_mouseclick(event.x(), event.y())
                editor.selectionbox_projected_origin = ray.origin + editor.camera_direction*0.01

            # Add object
            elif editor.mousemode == MOUSE_MODE_ADDWP:
                print("shooting rays")
                ray = editor.create_ray_from_mouseclick(event.x(), event.y())
                place_at = None

                if editor.collision is not None:
                    place_at = editor.collision.collide_ray(ray)

                if place_at is None:
                    print("colliding with plane")
                    plane = Plane.xy_aligned(Vector3(0.0, 0.0, 0.0))

                    collision = ray.collide_plane(plane)
                    if collision is not False:
                        place_at, _ = collision

                if place_at is not None:
                    print("collided")
                    editor.create_waypoint_3d.emit(place_at.x, place_at.z, -place_at.y)
                else:
                    print("nothing collided, aw")

            # Move object
            elif editor.mousemode == MOUSE_MODE_MOVEWP:
                mouse_x, mouse_z = (event.x(), event.y())
                ray = editor.create_ray_from_mouseclick(event.x(), event.y())

                if len(editor.selected) > 0:
                    average_height = 0
                    for pikminobj in editor.selected:
                        average_height += pikminobj.y + pikminobj.offset_y
                    average_height = average_height / len(editor.selected)

                    editor.move_collision_plane.origin.z = average_height
                    collision = ray.collide_plane(editor.move_collision_plane)
                    if collision is not False:
                        point, d = collision
                        movetox, movetoz = point.x, point.y

                        if len(editor.selected) > 0:
                            sumx, sumz = 0, 0
                            wpcount = len(editor.selected)
                            for obj in editor.selected:
                                sumx += obj.x
                                sumz += obj.z

                            x = sumx / float(wpcount)
                            z = sumz / float(wpcount)

                            editor.move_points.emit(movetox - x, -movetoz - z)

    def handle_release_3d(self, event):
        editor = self._editor_widget

        for key in key_enums.keys():
            if self.buttons.just_pressed(event, key):
                for action in self.clickdragactions3d[key]:
                    if action.condition(editor, self.buttons, event):
                        action.just_released(editor, self.buttons, event)

        return

        if self.buttons.just_released(event, "Right"):
            editor.last_move = None

        if self.buttons.just_released(event, "Left"):
            if editor.mousemode == MOUSE_MODE_NONE:
                startx, starty = editor.selectionbox_projected_2d

                minx = min(startx, event.x())
                maxx = max(startx, event.x())
                miny = min(starty, event.y())
                maxy = max(starty, event.y())

                width = maxx - minx
                height = maxy - miny

                editor.selection_queue.append((minx, maxy, width + 1, height + 1,
                                               editor.shift_is_pressed))

                editor.selectionbox_projected_2d = None
                editor.selectionbox_projected_origin = None
                editor.selectionbox_projected_right = None
                editor.selectionbox_projected_coords = None
                editor.do_redraw()

        editor.last_mouse_move = (event.x(), event.y())

    def handle_move_3d(self, event):
        editor = self._editor_widget

        for key in key_enums.keys():
            if self.buttons.just_pressed(event, key):
                for action in self.clickdragactions3d[key]:
                    if action.condition(editor, self.buttons, event):
                        action.move(editor, self.buttons, event)

        return

        if self.right_button_down and self.last_move is not None:
            curr_x, curr_y = event.x(), event.y()
            last_x, last_y = self.last_move

            diff_x = curr_x - last_x
            diff_y = curr_y - last_y

            self.last_move = (curr_x, curr_y)

            self.camera_horiz = (self.camera_horiz - diff_x * (pi / 500)) % (2 * pi)
            self.camera_vertical = (self.camera_vertical - diff_y * (pi / 600))
            if self.camera_vertical > pi / 2.0:
                self.camera_vertical = pi / 2.0
            elif self.camera_vertical < -pi / 2.0:
                self.camera_vertical = -pi / 2.0

            # print(self.camera_vertical, "hello")
            self.do_redraw()

        if self.left_button_down:
            if self.mousemode == MOUSE_MODE_NONE and self.selectionbox_projected_2d is not None:
                self.camera_direction.normalize()

                view = self.camera_direction.copy()

                h = view.cross(Vector3(0, 0, 1))
                v = h.cross(view)

                h.normalize()
                v.normalize()

                rad = 75 * pi / 180.0
                vLength = tan(rad / 2) * 1.0
                hLength = vLength * (self.canvas_width / self.canvas_height)

                v *= vLength
                h *= hLength

                mirror_y = self.canvas_height - event.y()
                halfwidth = self.canvas_width / 2
                halfheight = self.canvas_height / 2

                x = event.x() - halfwidth
                y = (self.canvas_height - event.y()) - halfheight
                startx = (self.selectionbox_projected_2d[0] - halfwidth) / halfwidth
                starty = (self.canvas_height - self.selectionbox_projected_2d[1] - halfheight) / halfheight

                x /= halfwidth
                y /= halfheight
                camerapos = Vector3(self.offset_x, self.offset_z, self.camera_height)

                self.selectionbox_projected_coords = (
                    camerapos + view * 1.01 + h * startx + v * y,
                    camerapos + view * 1.01 + h * x + v * y,
                    camerapos + view * 1.01 + h * x + v * starty
                )

                # print("ok", self.selectionbox_projected_right)
                self.do_redraw()
            if self.mousemode == MOUSE_MODE_MOVEWP:
                ray = self.create_ray_from_mouseclick(event.x(), event.y())

                if len(self.selected) > 0:
                    average_origin = Vector3(0.0, 0.0, 0.0)

                    for pikminobj in self.selected:
                        average_origin += Vector3(pikminobj.x + pikminobj.offset_x,
                                                  pikminobj.y + pikminobj.offset_y,
                                                  pikminobj.z + pikminobj.offset_z)

                    average_origin = average_origin / len(self.selected)

                    if not self.change_height_is_pressed:
                        self.move_collision_plane.origin.z = average_origin.y
                        collision = ray.collide_plane(self.move_collision_plane)
                        if collision is not False:
                            point, d = collision
                            movetox, movetoz = point.x, point.y

                            if self.rotation_is_pressed and len(self.selected) == 1:
                                obj = self.selected[0]
                                relx = obj.x - movetox
                                relz = -obj.z - movetoz

                                self.rotate_current.emit(obj, degrees(atan2(-relx, relz)))

                            elif not self.rotation_is_pressed:
                                if len(self.selected) > 0:
                                    sumx, sumz = 0, 0
                                    wpcount = len(self.selected)
                                    for obj in self.selected:
                                        sumx += obj.x
                                        sumz += obj.z

                                    x = sumx / float(wpcount)
                                    z = sumz / float(wpcount)

                                    self.move_points.emit(movetox - x, -movetoz - z)
                    else:
                        """
                        # Method of raising/lowering height:
                        # objects are moved to where the mouse goes
                        normal = self.camera_direction.copy()
                        normal.z = 0.0
                        normal.normalize()
                        tempz = average_origin.z
                        average_origin.z = average_origin.y
                        average_origin.y = -tempz

                        collision_plane = Plane.from_implicit(average_origin, normal)
                        collision = ray.collide_plane(collision_plane)
                        if collision is not False:

                            point, d = collision

                            delta_y = point.z - average_origin.z
                            print("hit", point, average_origin)
                            print(delta_y, normal)
                            if len(self.selected) > 0:
                                self.height_update.emit(delta_y)"""

                        tempz = average_origin.z
                        average_origin.z = average_origin.y
                        average_origin.y = -tempz
                        campos = Vector3(self.offset_x, self.offset_z, self.camera_height)
                        dist = (campos - average_origin).norm()
                        fac = min(5.0, max(0.5, dist / 200.0))
                        print(dist, fac)
                        delta_height = -1 * (event.y() - self.last_mouse_move[1])
                        if len(self.selected) > 0:
                            self.height_update.emit(delta_height * fac)
