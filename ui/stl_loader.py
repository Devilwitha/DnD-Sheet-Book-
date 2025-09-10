"""
STL Loader for Kivy3
"""
import numpy as np
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
            return obj

        # Combine all vertices into a single array for bounding box calculation
        all_vertices = np.concatenate([stl_mesh.v0, stl_mesh.v1, stl_mesh.v2])

        if all_vertices.size == 0:
            Logger.warning("STLLoader: STL file contains no vertices.")
            return obj

        # --- Auto-scaling and Centering ---
        # Calculate bounding box
        min_coords = np.min(all_vertices, axis=0)
        max_coords = np.max(all_vertices, axis=0)
        center = (min_coords + max_coords) / 2.0

        # Calculate scale factor
        bounding_box_size = max_coords - min_coords
        max_dimension = np.max(bounding_box_size)

        # Avoid division by zero for empty or flat models
        if max_dimension < 1e-6:
            scale_factor = 1.0
        else:
            TARGET_SIZE = 20.0  # The desired size for the largest dimension
            scale_factor = TARGET_SIZE / max_dimension

        Logger.info(f"STLLoader: Scaling factor: {scale_factor}, Center: {center}")

        geometry = Geometry()
        # Use a brighter material for better visibility
        material = Material(color=(0.8, 0.8, 0.8), diffuse=(0.7, 0.7, 0.7), specular=(0.2, 0.2, 0.2), shininess=10.0)

        for i in range(len(stl_mesh.v0)):
            # Apply transformation: center the model at origin and then scale it
            v0 = (stl_mesh.v0[i] - center) * scale_factor
            v1 = (stl_mesh.v1[i] - center) * scale_factor
            v2 = (stl_mesh.v2[i] - center) * scale_factor

            normal = stl_mesh.normals[i]

            idx = len(geometry.vertices)

            geometry.vertices.append(v0.tolist())
            geometry.vertices.append(v1.tolist())
            geometry.vertices.append(v2.tolist())

            face = Face3(idx, idx + 1, idx + 2)
            face.vertex_normals.append(normal.tolist())
            face.vertex_normals.append(normal.tolist())
            face.vertex_normals.append(normal.tolist())

            geometry.faces.append(face)

        Logger.info("STLLoader: Geometry creation loop finished.")

        try:
            kivy_mesh = Mesh(geometry, material)
            Logger.info("STLLoader: Kivy3 mesh created successfully.")
        except Exception as e:
            Logger.error(f"STLLoader: Failed to create Kivy3 mesh: {e}")
            return obj

        obj.add(kivy_mesh)
        Logger.info("STLLoader: Mesh added to Object3D.")
        return obj
