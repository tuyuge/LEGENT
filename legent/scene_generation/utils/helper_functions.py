from shapely.geometry import LineString, MultiLineString, Polygon, Point
import matplotlib.pyplot as plt
import random
import re
import objaverse
import numpy as np
from shapely.geometry import Polygon
from shapely.affinity import rotate
from legent import load_json, Environment, ResetInfo, SaveTopDownView, Observation, TakePhotoWithVisiblityInfo
import trimesh
from legent.utils.config import ENV_FOLDER
objaverse._VERSIONED_PATH = f"{ENV_FOLDER}/objaverse"
from legent.scene_generation.utils.mesh_processer import convert_holodeck_asset_to_gltf
import os
from legent.utils.math import look_rotation
import copy


######## legent related ########
def take_photo(scene, folder, camera_width=4096, camera_field_of_view=120, vertical_field_of_view=90, photo_type="player_view"):
    """
    Take a photo of the scene and save it to the abosulte path!
    """
    env = Environment(env_path="auto", camera_resolution=1024, camera_field_of_view=camera_field_of_view)
    camera_height = int(camera_width / camera_field_of_view * vertical_field_of_view)
    try:
        if photo_type == "topdown":
            photo_path = f"{folder}/topdown.png"
            obs = env.reset(ResetInfo(scene, api_calls=[SaveTopDownView(absolute_path=photo_path)]))
        elif photo_type == "player_view":
            photo_path = f"{folder}/player_view.png"
            position = scene["player"]["position"].copy()
             # player look at the center
            vs, vt = np.array([position[0],0, position[2]]), np.array([0, 0, 0])
            vr = look_rotation(vt - vs)
            offset = random.uniform(-30, 30)
            rotation = [0, vr[1]+offset, 0]
            position[1] = 1
            scene["player"]["position"] = [50, 0.1, 50]
            obs = env.reset(ResetInfo(scene, api_calls=[TakePhotoWithVisiblityInfo(photo_path, position, rotation, width=camera_width, height=camera_height, vertical_field_of_view=vertical_field_of_view)]))
        print("Scene saved successfully: ", photo_path)
    finally:
        env.close()

def play_with_scene(scene):
    """
    Play with the scene
    """
    env = Environment(env_path="auto", camera_resolution=1024, camera_field_of_view=120)
    try:
        obs: Observation = env.reset(ResetInfo(scene=scene))
        while True:
            obs = env.step()
    finally:
        env.close()

def complete_scene(predefined_scene):
    """
    Complete a predefined scene by adding player, agent, interactable information etc.
    """
    # Helper function to get the center of the scene
    # def get_center(predefined_scene):
    #     bboxes = [floor["bbox"] for floor in predefined_scene["floors"]]
    #     x_min = min(bbox[0] for bbox in bboxes)
    #     z_min = max(bbox[1] for bbox in bboxes)
    #     x_max = min(bbox[2] for bbox in bboxes)
    #     z_max = max(bbox[3] for bbox in bboxes)
    #     center = [(x_min + x_max) / 2, (z_min + z_max) / 2]
    #     return [center[0], (x_max-x_min+z_max-z_min), center[1]]

    position = [100, 0.1, 100] 
    rotation = [0, random.randint(0, 360), 0]
    agent = {
        "prefab": "",
        "position": position,
        "rotation": rotation,
        "scale": [1, 1, 1],
        "parent": -1,
        "type": ""
    }

    # center of one room
    bbox = predefined_scene["floors"][0]["bbox"]
    x_min, z_min, x_max, z_max = bbox
    center = [(x_min + x_max) / 2,(x_max-x_min+z_max-z_min), (z_min + z_max) / 2]


     # if the player can not be placed, then place it at the door
    door_position = next(instance for instance in predefined_scene["instances"] if instance["category"]=="door")["position"]
    player_position = copy.deepcopy(door_position)
    player_position = [player_position[0], 0.1, player_position[2]+0.3]
    rotation = [0, 45, 0]
    player = {
        "prefab": "",
        "position": player_position,
        "rotation": rotation,
        "scale": [1, 1, 1],
        "parent": -1,
        "type": ""
    }

    infos = {
        "prompt": "",
        "floors": predefined_scene["floors"] if "floors" in predefined_scene else [],
        "walls": predefined_scene["walls"] if "walls" in predefined_scene else [],
        "instances": predefined_scene["instances"] if "instances" in predefined_scene else [],
        "player": predefined_scene["player"] if "player" in predefined_scene and predefined_scene["player"] else player,
        "agent": predefined_scene["agent"] if "agent" in predefined_scene and predefined_scene["agent"] else agent,
        "center": predefined_scene["center"] if "center" in predefined_scene else center,
    }
    return infos
        
class PolygonConverter:
    """
    instance: position, rotation, size
    polygon: Polygon object
    vertices: [(x1, z1), (x2, z2), (x3, z3), (x4, z4), ...]
    bbox: [xmin, zmin, xmax, zmax]
    surfaces: {"xz": [x_min, z_min, x_max, z_max], "y": y, direction: direction}
    """
    def __init__(self, wall_width=0):
        self.wall_width = wall_width
    
    # get surface before placing the object
    def get_surfaces(self, instance):
        for surface in instance["surfaces"]:
            if "direction" not in surface:
                if instance["category"] in ["wall", "window", "door"]:
                    surface["direction"] = [90, 0, 0]
                elif instance["category"] == "ceiling":
                    surface["direction"] = [180, 0, 0]
                else:
                    surface["direction"] = [0, 0, 0]
            if "xz" not in surface:
                if "placeable_surfaces" in instance and instance["placeable_surfaces"] and surface["direction"] == [0, 0, 0]:
                    surface = self.get_placeable_surface(surface, instance["placeable_surfaces"])
                else:
                    surface = self.instance_to_surface(surface, instance)
        return instance
    
    def get_bbox(self, position_xz, size_xz):
        """
        Get the bounding box of an instance
        """
        vertices = self.get_rectangle_relative_vertices(position_xz, size_xz)
        polygon = self.vertcies_to_polygon(vertices, 0)
        return polygon.bounds

    def get_placeable_surface(self, surface, placeable_surfaces):
        """
        Get the placeable surface of an instance
        """
        placeable_surface = random.choice(placeable_surfaces)
        surface["xz"] = placeable_surface["x_min"], placeable_surface["z_min"], placeable_surface["x_max"], placeable_surface["z_max"]
        surface["y"] = placeable_surface["y"]
        return surface

    def instance_to_surface(self, surface, instance):
        size = PolygonConverter().rotate_3D(instance["size"], surface["direction"])
        if instance["category"] in ["floor", "ceiling", "wall"]:
            size = [abs(size[0])-self.wall_width, abs(size[1]), abs(size[2])-self.wall_width]
        size = [abs(size[0]), abs(size[1]), abs(size[2])]
        vertices = self.get_rectangle_relative_vertices([0, 0], size[0:3:2])
        polygon = self.vertcies_to_polygon(vertices, 0)
        surface.update({
            "xz": polygon.bounds,
            "y": size[1]/2
        })
        return surface

    @staticmethod
    def vertcies_to_polygon(vertices, angle):
        """
        Get the polygon given all vertices and angle
        """
        polygon = Polygon(vertices)
        rotated_polygon = rotate(polygon, -angle, origin='center')
        return rotated_polygon
    
    @staticmethod
    def get_rectangle_relative_vertices(position, size):
        """
        Get the vertices of a rectangle given the position and size; note that x1, x2 can be x,z or x,y
        """
        x1, x2 = position
        length, width = size
        x1_min, x1_max = x1 - length / 2, x1 + length / 2
        x2_min, x2_max = x2 - width / 2, x2 + width / 2
        return [(x1_min, x2_min), (x1_max, x2_min), (x1_max, x2_max), (x1_min, x2_max)]

    @staticmethod
    def bbox_dimensions(bbox):
        """
        Calculate the length, width, center of a bbox
        """
        min_x1, min_x2, max_x1, max_x2 = bbox
        length = max_x1 - min_x1
        width = max_x2 - min_x2
        center = [(min_x1 + max_x1) / 2, (min_x2 + max_x2) / 2]
        return length, width, center
    
    @staticmethod
    def rotate_3D(point, angles):
        """
        rotate a point in 3D space using given angles about the X, Y, and Z axes
        """
        angle_x, angle_y, angle_z = np.deg2rad(angles)
        
        # Rotation matrix for rotation about the X-axis
        Rx = np.array([
            [1, 0, 0],
            [0, np.cos(angle_x), -np.sin(angle_x)],
            [0, np.sin(angle_x), np.cos(angle_x)]
        ])
        
        # Rotation matrix for rotation about the Y-axis
        Ry = np.array([
            [np.cos(angle_y), 0, np.sin(angle_y)],
            [0, 1, 0],
            [-np.sin(angle_y), 0, np.cos(angle_y)]
        ])
        
        # Rotation matrix for rotation about the Z-axis
        Rz = np.array([
            [np.cos(angle_z), -np.sin(angle_z), 0],
            [np.sin(angle_z), np.cos(angle_z), 0],
            [0, 0, 1]
        ])
        
        # Composite rotation matrix, order of multiplication depends on rotation sequence
        R = np.dot(Rz, np.dot(Ry, Rx))
        
        # Rotate the point
        rotated_point = np.dot(R, point)
        return rotated_point.tolist()

class InstanceGenerator:
    def __init__(self, use_objaverse=False, use_holodeck=False):
        self.use_objaverse = use_objaverse
        self.use_holodeck = use_holodeck
        self.holodeck_data_path = "/Users/a0001/THUNLP/embodied_ai/Holodeck-main/data/objaverse_holodeck/09_23_combine_scale/processed_2023_09_23_combine_scale"
        self.prefab_to_asset = load_json("legent/scene_generation/data/prefab_to_asset.json")
        self.object_types_to_instances = load_json("legent/scene_generation/data/object_type_to_instances.json")

    def get_instance(self, instance):
        """
        Get the instance given the prefab or category, add scale and reset size
        """
        # get the asset
        if "prefab" not in instance:
            asset = random.choice(self.object_types_to_instances[instance["category"]])
        else:
            asset = self.prefab_to_asset[instance["prefab"]]
        
        try:
            asset['size'] = [asset['size'][dim] for dim in ('x', 'y', 'z')]
        except:
            pass

        asset["prefab"] = self._reset_prefab(asset["name"])
        if asset["type"] is None:
            asset["type"] = "kinematic"
        
        instance.update(asset)
           
        try:
            instance["scale"] = self._get_scale(instance["prefab"], instance["size"])
        except:
            instance["scale"] = [1,1,1]

        return instance        

    def _reset_prefab(self, prefab):
        """
        Set prefab attribute for the instance
        """
        if self.use_objaverse:
            try:
                prefab = self._objaverse_object(prefab)
            except:
                prefab = prefab
        elif self.use_holodeck:
            try:
                prefab = self._holodeck_object(prefab)
            except:
                prefab = prefab
        return prefab
    
    @staticmethod
    def prefab_to_category(prefab):
        """
        Get the category according to prefab
        """
        pattern = re.compile(r'[a-zA-Z]{2,}', re.IGNORECASE)
        match = pattern.findall(prefab)
        category = "_".join(match[1:])
        return category.lower()
    
    def _objaverse_object(self, uid):
        objects = objaverse.load_objects([uid])
        return list(objects.values())[0]
    
    def _holodeck_object(self, uid):
        asset = None
        convert_holodeck_asset_to_gltf(f"{self.holodeck_data_path}/{uid}", f".data/{uid}.gltf")
        # Add Holodeck example
        asset = os.path.abspath(f".data/{uid}.gltf")
        return asset
    
    def _calculate_bounding_box_from_trimesh(self, file_path):
        mesh = trimesh.load(file_path)
        return mesh.bounds[0], mesh.bounds[1]

    def _get_scale(self, file_path, size):
        min_vals, max_vals = self._calculate_bounding_box_from_trimesh(file_path)
        mesh_size = max_vals - min_vals
        scale = size / mesh_size
        scale = list(scale)
        return scale

class RectangleProcessor:
    def __init__(self):
        self.boundaries = []
        self.rects = []

    def process_new_rectangle(self, rect_coords, plot=False):
        """Processes a new rectangle, updating boundaries and computing remaining edges."""
        rectangle = Polygon(rect_coords)
        boundary = rectangle.exterior.coords
        
        total_intersection = self._compute_total_intersection(boundary)

        # add the new boundary and rectangle to the list after subtracting the intersection
        self.boundaries.append(boundary)
        self.rects.append(rect_coords)
        if plot:
            self._plot_multiple_polygons(self.rects)

        return self._subtract_intersection_from_boundary(boundary, total_intersection)

    def _compute_total_intersection(self, boundary):
        """Computes the total intersection of the new boundary with all existing boundaries."""
        new_line = LineString(boundary)
        total_intersection = LineString()
        
        for existing_boundary in self.boundaries:
            intersection = new_line.intersection(LineString(existing_boundary))
            total_intersection = total_intersection.union(intersection)
            
        return total_intersection

    def _subtract_intersection_from_boundary(self, boundary, total_intersection):
        """Subtracts the total intersection from the boundary, returning remaining edges."""
        remaining_edges = []
        
        for i in range(len(boundary) - 1):
            rotation = (4-i) * 90 if i != 0 else 0
            edge = LineString([boundary[i], boundary[i + 1]])
            difference = edge.difference(total_intersection)
            
            if isinstance(difference, LineString):
                if not difference.is_empty:
                    remaining_edges.append({"rotation":rotation, "vertices":list(difference.coords), "length":difference.length})
            elif isinstance(difference, MultiLineString):
                new_edges = [{"rotation":rotation, "vertices":list(segment.coords), "length":segment.length} for segment in difference.geoms if not segment.is_empty]
                remaining_edges.extend(new_edges)
        return remaining_edges

    def _plot_multiple_polygons(self, polygons, save_path=None, save=False):
        """
        Plot multiple polygons with the option to draw a bounding box around them.
        """
        # set the figsize to be square
        plt.figure(figsize=(10, 10)) 
        for polygon in polygons:
            x = [vertex[0] for vertex in polygon]
            y = [vertex[1] for vertex in polygon]
            plt.plot(x + [x[0]], y + [y[0]])
        
        # Set aspect of the plot to be equal, so squares appear as squares
        plt.gca().set_aspect('equal')
        plt.gca().autoscale_view()

        # Turn off the axis
        plt.axis('off')
        
        if save:plt.savefig(save_path)
        else:plt.show()


if __name__ == "__main__":
    rect1 = [(0,0), (2,0), (2,2), (0,2)]
    rect2 = [(2,0), (2,2), (4,2), (4,0)]
    rect3 = [(1,2), (3,2), (3,4), (1,4)]
    rect4 = [(3,2), (5,2), (5,4), (3,4)]
    polygons = [rect1, rect2, rect3, rect4]

    rect_processor = RectangleProcessor()
    remaining_edges = rect_processor.process_new_rectangle(rect1)
    print(remaining_edges)

    remaining_edges = rect_processor.process_new_rectangle(rect2)
    print(remaining_edges)

    remaining_edges = rect_processor.process_new_rectangle(rect3)
    print(remaining_edges)

    remaining_edges = rect_processor.process_new_rectangle(rect4)
    print(remaining_edges)