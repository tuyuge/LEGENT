from shapely.geometry import LineString, MultiLineString, Polygon, Point
import matplotlib.pyplot as plt
import random
import re
import objaverse
import numpy as np
from shapely.geometry import Polygon
from shapely.geometry import box
from shapely.affinity import rotate
from legent import load_json, store_json, Environment, ResetInfo, SaveTopDownView, Observation
from legent.utils.config import ENV_FOLDER
objaverse._VERSIONED_PATH = f"{ENV_FOLDER}/objaverse"

######## legent related ########
def take_photo(generator, room_plans, folder):
    """
    Take a photo of the scene and save it to the abosulte path!
    """
    env = Environment(env_path="auto", camera_resolution=1024, camera_field_of_view=120)

    try:
        scene = generator(room_plans)
        store_json(scene, f"{folder}/scene.json")
        photo_path = f"{folder}/photo.png"
        obs = env.reset(ResetInfo(scene, api_calls=[SaveTopDownView(absolute_path=photo_path)]))
        print("Scene saved successfully: ", photo_path)
    finally:
        env.close()

def play_with_scene(scene_path, generator, room_plans, scene_folder):
    """
    Play with the scene
    """
    env = Environment(env_path="auto", camera_resolution=1024, camera_field_of_view=120)
    try:
        obs: Observation = env.reset(ResetInfo(scene=load_json(scene_path)))
        while True:
            if obs.text == "#RESET":
                scene = generator(room_plans)
                env.reset(ResetInfo(scene))
                store_json(scene, f"{scene_folder}/scene.json")
            obs = env.step()
    finally:
        env.close()

def complete_scene(predefined_scene):
    """
    Complete a predefined scene by adding player, agent, interactable information etc.
    """
    # Helper function to get the center of the scene
    def get_center(predefined_scene):
        bboxes = [floor["bbox"] for floor in predefined_scene["floors"] if "bbox" in floor]
        x_min = min(bbox[0] for bbox in bboxes)
        x_max = max(bbox[1] for bbox in bboxes)
        z_min = min(bbox[2] for bbox in bboxes)
        z_max = max(bbox[3] for bbox in bboxes)
        center = [(x_min + x_max) / 2, (z_min + z_max) / 2]
        return [center[0], (x_max-x_min+z_max-z_min)*2, center[1]]


    position = [100, 0.1, 100] 
    rotation = [0, random.randint(0, 360), 0]
    player = {
        "prefab": "",
        "position": position,
        "rotation": rotation,
        "scale": [1, 1, 1],
        "parent": -1,
        "type": ""
    }

    position = [1.5, 0.1, 1.5]
    rotation = [0, random.randint(0, 360), 0]
    agent = {
        "prefab": "",
        "position": position,
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
        "player": predefined_scene["player"] if "player" in predefined_scene else player,
        "agent": predefined_scene["agent"] if "agent" in predefined_scene else agent,
        "center": predefined_scene["center"] if "center" in predefined_scene else get_center(predefined_scene),
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
    def rotate_bbox(bbox, angle):
        """
        Rotate a bounding box by a given angle
        """
        # Create a box from bounds
        x_min, z_min, x_max, z_max = bbox
        rect = box(x_min, z_min, x_max, z_max)
        origin = rect.centroid.coords[0]
        rotated_rect = rotate(rect, angle, origin=origin)
        x_min, z_min, x_max, z_max = rotated_rect.bounds
        return x_min, z_min, x_max, z_max
    
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

        
def get_object_pos(receptacle, surface, object, rotation):
    """
    Get the position of the object relative to the surface and the absolute position
    """

    def _get_position(instance, receptacle, surface, rotation):   
        """
        Get the position of the object relative to the surface
        """
        
        # get the size of the surface
        x_min, z_min, x_max, z_max = surface["xz"]
        # rotate the surface size, note that y axis is not affected
        if receptacle["category"] == "floor":
            x_min, z_min, x_max, z_max = PolygonConverter.rotate_bbox(surface["xz"], rotation[1])
            abs_size = instance["size"]
        else:
            # rotate the instance size
            rotated_size = PolygonConverter().rotate_3D(instance["size"], surface["direction"])
            abs_size = [abs(dim) for dim in rotated_size]

        x = random.uniform(x_min + abs_size[0] / 2, x_max - abs_size[0] / 2)
        z = random.uniform(z_min + abs_size[2] / 2, z_max - abs_size[2] / 2)
        y = abs_size[1]/2

        # Override x and z if 'relative_pos' is available in instance
        if "position_xz" in instance:
            if receptacle["category"] != "floor":
                position_x, position_z = instance["position_xz"]
                if position_x == "auto":
                    x = x_max - abs_size[0] / 2
                # if position_x is float or int
                elif isinstance(position_x, (int, float)):
                    x = position_x
                if position_z == "auto":
                    z = z_max - abs_size[2] / 2
                elif isinstance(position_z, (int, float)):
                    z = position_z
            else:
                position_x, position_z = instance["position_xz"]
                if position_x == "auto":
                    x = x_min + abs_size[0] / 2
                # if position_x is float or int
                elif isinstance(position_x, (int, float)):
                    x = position_x
                if position_z == "auto":
                    z = z_min + abs_size[2] / 2
                elif isinstance(position_z, (int, float)):
                    z = position_z

        relative_pos = x, y, z
        size_xz = abs_size[0:3:2]
        return relative_pos, size_xz
    
    # find the absolute position of a point relative to a cuboid that has been rotated
    # get the position of the object relative to the surface
    if object["category"] == "bedtable":
        pass
    object_to_surface_pos, size_xz = _get_position(object, receptacle, surface, rotation)
    # get the position of the point relative to the center of the cuboid 
    surface_to_receptacle_pos = [0,surface["y"],0]
    object_to_receptacle_pos = [x+y for x, y in zip(object_to_surface_pos, surface_to_receptacle_pos)]
    if object["category"] in ["door", "window"]:
        object_to_receptacle_pos[1] = 0
    # rotate the point using the given angles [angle_x, angle_y, angle_z]
    object_to_receptacle_pos = PolygonConverter.rotate_3D(object_to_receptacle_pos, rotation)
    # After applying the rotation, translate the rotated point back to its absolute position 
    object_position = [m + n for m, n in zip(receptacle["position"], object_to_receptacle_pos)]
    position_xz = object_to_surface_pos[0:3:2]
    if receptacle["category"] != "floor":
        position_xz = [position_xz[0], -position_xz[1]]
    else:
        position_xz = object_to_receptacle_pos[0:3:2]
    return position_xz, size_xz, object_position


class InstanceGenerator:
    def __init__(self, use_objaverse=False):
        self.use_objaverse = use_objaverse
        self.assets = self._get_assets()

    def get_instance(self, instance):
        prefab = instance["prefab"] if "prefab" in instance else None
        if "category" not in instance:
            category = self.get_category(instance["prefab"])
            instance["category"] = category
        else:
            category = instance["category"]
        """
        Get the instance given the category or prefab
        """

        try:
            if prefab:
                asset = next(item for item in self.assets[category] if item['name'] == prefab)
                
            else:
                asset = random.choice(self.assets[category])
            asset["prefab"] = self._set_prefab(asset['name'])

            try:
                asset['size'] = [asset['size'][dim] for dim in ('x', 'y', 'z')]
            except:
                print("Wrong: ", asset)
            
            instance.update(asset)
           
        except (KeyError, StopIteration):
            pass

        return instance
    
    def _get_assets(self):
        # Load prefab data
        if self.use_objaverse:
            asset_path = "legent/scene_generation/data/objaverse_prefabs.json"
        else:
            asset_path = "legent/scene_generation/data/prefabs.json"
        assets = load_json(asset_path)
        return assets
        

    def _set_prefab(self, instance_name):
        """
        Set prefab attribute for the instance
        """
        if instance_name not in ["agent", "player"]:
            if self.use_objaverse:
                prefab = self._objaverse_object(instance_name)
            else:
                prefab = instance_name
            return prefab
    
    @staticmethod
    def get_category(prefab):
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