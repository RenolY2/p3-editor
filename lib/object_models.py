
from OpenGL.GL import *
from .model_rendering import GenericObject


class ObjectModels(object):
    def __init__(self):
        self.models = {}
        self.generic = GenericObject()

    def render_object(self, pikminobject, selected):
        glPushMatrix()

        glTranslatef(pikminobject.position.x, -pikminobject.position.z, pikminobject.position.y)
        glRotate(pikminobject.rotation.x, 1, 0, 0)
        glRotate(pikminobject.rotation.y, 0, 0, -1)
        glRotate(pikminobject.rotation.z, 0, 1, 0)

        if pikminobject.name in self.models:
            self.models[pikminobject.name].render()
        else:
            self.generic.render(selected=selected)

        glPopMatrix()

    def render_object_coloredid(self, pikminobject, id):
        glPushMatrix()

        glTranslatef(pikminobject.position.x, -pikminobject.position.z, pikminobject.position.y)
        glRotate(pikminobject.rotation.x, 1, 0, 0)
        glRotate(pikminobject.rotation.y, 0, 0, -1)
        glRotate(pikminobject.rotation.z, 0, 1, 0)

        if pikminobject.name in self.models:
            self.models[pikminobject.name].render_coloredid(id)
        else:
            self.generic.render_coloredid(id)

        glPopMatrix()
