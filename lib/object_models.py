import os
import json
from OpenGL.GL import *
from .model_rendering import (GenericObject, Model, TexturedModel,
                              GenericFlyer, GenericCrystallWall, GenericLongLegs, GenericChappy, GenericSnakecrow,
                              GenericSwimmer)


class ObjectModels(object):
    def __init__(self):
        self.models = {}
        self.generic = GenericObject()
        self.generic_flyer = GenericFlyer()
        self.generic_longlegs = GenericLongLegs()
        self.generic_chappy = GenericChappy()
        self.generic_snakecrow = GenericSnakecrow()
        self.generic_swimmer = GenericSwimmer()

        genericmodels = {
            "Chappy": self.generic_chappy,
            "Flyer": self.generic_flyer,
            "Longlegs": self.generic_longlegs,
            "Snakecrow": self.generic_snakecrow,
            "Swimmer": self.generic_swimmer
        }

        with open("resources/enemy_model_mapping.json", "r") as f:
            mapping = json.load(f)
            for enemytype, enemies in mapping.items():
                if enemytype in genericmodels:
                    for name in enemies:
                        self.models[name.title()] = genericmodels[enemytype]

        with open("resources/unitsphere.obj", "r") as f:
            self.sphere = Model.from_obj(f, rotate=True)

        with open("resources/unitcylinder.obj", "r") as f:
            self.cylinder = Model.from_obj(f, rotate=True)

    def init_gl(self):
        for dirpath, dirs, files in os.walk("resources/objectmodels"):
            for file in files:
                if file.endswith(".obj"):
                    filename = os.path.basename(file)
                    objectname = filename.rsplit(".", 1)[0]
                    self.models[objectname] = TexturedModel.from_obj_path(os.path.join(dirpath, file), rotate=True)

        # self.generic_wall = TexturedModel.from_obj_path("resources/generic_object_wall2.obj", rotate=True, scale=20.0)

    def draw_sphere(self, position, scale):
        glPushMatrix()

        glTranslatef(position.x, -position.z, position.y)
        glScalef(scale, scale, scale)

        self.sphere.render()
        glPopMatrix()

    def draw_sphere_last_position(self, scale):
        glPushMatrix()

        glScalef(scale, scale, scale)

        self.sphere.render()
        glPopMatrix()

    def draw_cylinder(self,position, radius, height):
        glPushMatrix()

        glTranslatef(position.x, -position.z, position.y)
        glScalef(radius, height, radius)

        self.cylinder.render()
        glPopMatrix()

    def draw_cylinder_last_position(self, radius, height):
        glPushMatrix()

        glScalef(radius, radius, height)

        self.cylinder.render()
        glPopMatrix()

    def render_object(self, pikminobject, selected):
        glPushMatrix()

        glTranslatef(pikminobject.position.x, -pikminobject.position.z, pikminobject.position.y)

        if "mEmitRadius" in pikminobject.unknown_params and pikminobject.unknown_params["mEmitRadius"] > 0:
            self.draw_cylinder_last_position(pikminobject.unknown_params["mEmitRadius"]/2, 50.0)

        if "mRadius" in pikminobject.unknown_params:
            if len(pikminobject.unknown_params["mRadius"]) >= 1 and float(pikminobject.unknown_params["mRadius"][0]) > 0:
                rad = float(pikminobject.unknown_params["mRadius"][0])
                self.draw_cylinder_last_position(rad/2, 50.0)

        glRotate(pikminobject.rotation.x, 1, 0, 0)
        glRotate(pikminobject.rotation.y, 0, 0, 1)
        glRotate(pikminobject.rotation.z, 0, 1, 0)

        if pikminobject.name in self.models:
            self.models[pikminobject.name].render(selected=selected)
        else:
            glDisable(GL_TEXTURE_2D)
            self.generic.render(selected=selected)

        glPopMatrix()

    def render_object_coloredid(self, pikminobject, id):
        glPushMatrix()

        glTranslatef(pikminobject.position.x, -pikminobject.position.z, pikminobject.position.y)
        glRotate(pikminobject.rotation.x, 1, 0, 0)
        glRotate(pikminobject.rotation.y, 0, 0, 1)
        glRotate(pikminobject.rotation.z, 0, 1, 0)

        if pikminobject.name in self.models:
            self.models[pikminobject.name].render_coloredid(id)
        else:
            self.generic.render_coloredid(id)


        glPopMatrix()
