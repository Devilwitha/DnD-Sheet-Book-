"""
STL Loader for Kivy3
"""
from stl import mesh
from kivy.logger import Logger
from kivy3 import Object3D, Mesh, Material
from kivy3.core.geometry import Geometry
from kivy3.core.face3 import Face3

class STLLoader:
    def __init__(self, **kwargs):
        self.source = kwargs.get("source")

    def load(self, source, **kw):
        self.source = source
        return self.parse()

    def parse(self):
        Logger.info("STLLoader: Starting to parse STL file...")
        obj = Object3D()
        try:
            stl_mesh = mesh.Mesh.from_file(self.source)
            Logger.info(f"STLLoader: Loaded {self.source} with {len(stl_mesh.vectors)} triangles.")
        except Exception as e:
            Logger.error(f"STLLoader: Failed to load STL file with numpy-stl: {e}")
            return obj # Return an empty object on failure

        geometry = Geometry()
        material = Material(color=(0.5, 0.5, 0.5), diffuse=(0.5, 0.5, 0.5), specular=(0.1, 0.1, 0.1), shininess=0.5)

        for i in range(len(stl_mesh.v0)):
            v0 = stl_mesh.v0[i]
            v1 = stl_mesh.v1[i]
            v2 = stl_mesh.v2[i]

            normal = stl_mesh.normals[i]

            idx = len(geometry.vertices)

            geometry.vertices.append(v0)
            geometry.vertices.append(v1)
            geometry.vertices.append(v2)

            face = Face3(idx, idx + 1, idx + 2)
            face.vertex_normals.append(normal)
            face.vertex_normals.append(normal)
            face.vertex_normals.append(normal)

            geometry.faces.append(face)

        Logger.info("STLLoader: Geometry creation loop finished.")

        try:
            kivy_mesh = Mesh(geometry, material)
            Logger.info("STLLoader: Kivy3 mesh created successfully.")
        except Exception as e:
            Logger.error(f"STLLoader: Failed to create Kivy3 mesh: {e}")
            return obj # Return an empty object on failure

        obj.add(kivy_mesh)
        Logger.info("STLLoader: Mesh added to Object3D.")
        return obj
