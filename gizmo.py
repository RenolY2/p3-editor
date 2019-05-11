from OpenGL.GL import *

from lib.model_rendering import Model
from lib.vectors import Vector3, Plane

id_to_meshname = {
    0x1: "gizmo_x",
    0x2: "gizmo_y",
    0x3: "gizmo_z",
    0x4: "rotation_x",
    0x5: "rotation_y",
    0x6: "rotation_z"
}


class Gizmo(Model):
    def __init__(self):
        super().__init__()

        self.position = Vector3(0.0, 0.0, 0.0)
        self.hidden = True#True

        self.callbacks = {}

    def move_to_average(self, objects):
        if len(objects) == 0:
            self.hidden = True
            return
        self.hidden = False

        avgx = None
        avgy = None
        avgz = None

        for obj in objects:
            if avgx is None:
                avgx = obj.position.x
                avgy = obj.position.y
                avgz = obj.position.z
            else:
                avgx += obj.position.x
                avgy += obj.position.y
                avgz += obj.position.z
        self.position.x = avgx / len(objects)
        self.position.y = avgy / len(objects)
        self.position.z = avgz / len(objects)
        print("New position is", self.position, len(objects))

    def render_collision_check(self, scale):
        if not self.hidden:
            glPushMatrix()
            glTranslatef(self.position.x, -self.position.z, self.position.y)
            glScalef(scale, scale, scale)

            self.named_meshes["gizmo_x"].render_colorid(0x1)
            self.named_meshes["gizmo_y"].render_colorid(0x2)
            self.named_meshes["gizmo_z"].render_colorid(0x3)
            self.named_meshes["rotation_x"].render_colorid(0x4)
            self.named_meshes["rotation_y"].render_colorid(0x5)
            self.named_meshes["rotation_z"].render_colorid(0x6)
            glPopMatrix()

    def register_callback(self, gizmopart, func):
        assert gizmopart in self.named_meshes

        self.callbacks[gizmopart] = func

    def run_callback(self, hit_id):
        meshname = id_to_meshname[hit_id]
        if meshname in self.callbacks:
            self.callbacks[meshname]()

    def render(self):
        if not self.hidden:
            for mesh in self.mesh_list:
                if "_x" in mesh.name:
                    glColor4f(1.0, 0.0, 0.0, 1.0)

                elif "_y" in mesh.name:
                    glColor4f(0.0, 1.0, 0.0, 1.0)

                elif "_z" in mesh.name:
                    glColor4f(0.0, 0.0, 1.0, 1.0)

                else:
                    glColor4f(0.5, 0.5, 0.5, 1.0)
                mesh.render()

    def render_scaled(self, scale):
        if not self.hidden:
            glPushMatrix()
            glTranslatef(self.position.x, -self.position.z, self.position.y)
            glScalef(scale, scale, scale)
            self.render()
            glPopMatrix()

