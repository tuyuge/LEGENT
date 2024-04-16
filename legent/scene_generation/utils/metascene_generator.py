from shapely.geometry import Polygon
from shapely.affinity import rotate
import random
from legent.server.rect_placer import RectPlacer
from legent import store_json, load_json
from legent_related import complete_scene, take_photo
from constants import FLOOR_MATERIAL, WALL_MATERIAL, WALL_HEIGHT, WALL_WIDTH
import numpy as np
import re
import os


####### Helper functions ########
class Prefab:
    def __init__(self):
        pass

    @staticmethod
    def get_instance(category, prefab=None):
        """
        Get the instance given the category or prefab
        """
        # Load prefab data
        assets = load_json("legent/scene_generation/data/prefabs.json")
        try:
            if prefab:
                instance = next(item for item in assets[category] if item['name'] == prefab)
            else:
                instance = random.choice(assets[category])
        except (KeyError, StopIteration):
            instance = {}
            prefab = category

        instance['prefab'] = prefab or instance['name']
        if 'size' in instance:
            instance['size'] = [instance['size'][dim] for dim in ('x', 'y', 'z')]
        
        return instance
    
    @staticmethod
    def get_category(prefab):
        """
        Get the category according to prefab
        """
        pattern = re.compile(r'[a-zA-Z]{2,}', re.IGNORECASE)
        match = pattern.findall(prefab)
        category = "_".join(match[1:])
        return category
    
class PolygonConverter:
    """
    instance: position, rotation, size
    polygon: Polygon object
    vertices: [(x1, y1), (x2, y2), (x3, y3), (x4, y4), ...]
    bbox: [xmin, ymin, xmax, ymax]
    surfaces: {"xz": [x_min, z_min, x_max, z_max], "y": y, direction: direction}
    """
    def __init__(self):
        pass
    
    # get surface before placing the object
    def get_surfaces(self, instance):
        for surface in instance["surfaces"]:
            if "direction" not in surface:
                if instance["category"].lower() in ["wall", "window", "door"]:
                    surface["direction"] = [-90, 0, 0]
                else:
                    surface["direction"] = [0, 0, 0]
            if "xz" not in surface:
                if "placeable_surfaces" in instance and instance["placeable_surfaces"] and surface["direction"] == [0, 0, 0]:
                    surface = self.get_placeable_surface(surface, instance["placeable_surfaces"])
                else:
                    surface = self.instance_to_surface(surface, instance)
        return instance
    
    def get_bbox(self, position, size):
        """
        Get the bounding box of an instance
        """
        vertices = self.get_rectangle_vertices(position[0:3:2], size[0:3:2])
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
        size = instance["size"]
        size = PolygonConverter().rotate_3D(size, surface["direction"])
        size = [abs(size[0]), abs(size[1]), abs(size[2])]
        vertices = self.get_rectangle_vertices([0, 0], size[0:3:2])
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
    def get_rectangle_vertices(position, size):
        """
        Get the vertices of a rectangle given the position and size; note that x1, x2 can be x,z or x,y
        """
        x1, x2 = position
        length, width = size
        x1_min, x1_max = x1 - length / 2, x2 + length / 2
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

class PositionGenerator:
    def __init__(self):
        pass

    def get_position(self, instance, surface):
        """
        Get the position of the instance
        """
        if "relative_pos" in instance:
            relative_pos = instance["relative_pos"]
        else:
            relative_pos = None
        x, y, z = self.get_random_pos(instance["category"], surface, instance["size"], relative_pos)
        return x, y, z

    def get_random_pos(self, category, surface, size, relative_pos):   
        size = PolygonConverter().rotate_3D(size, surface["direction"])   
        size = [abs(size[0]), abs(size[1]), abs(size[2])]  
        y = size[1]/2
        length, width, _ = PolygonConverter.bbox_dimensions(surface["xz"])
        
        try:
            x, z = relative_pos
        except:
            x = relative_pos
            if x != None:
                z = random.uniform(-width/2+size[2]/2, width/2-size[2]/2)
            else:
                x = random.uniform(-length/2+size[0]/2, length/2-size[0]/2)
                z = random.uniform(-width/2+size[2]/2, width/2-size[2]/2)
        if category == "Door":
            y = - WALL_WIDTH/2
            z = size[2]/2 - width/2
        if category == "Window":
            y = - WALL_WIDTH/2
        return x, y, z


def generate_floor_walls(object_plans):
    wall_material = random.choice(WALL_MATERIAL)


    def get_wall_rotation_pos(length, width):
        walls = []
        for i in range(4):
            rotation_y = i * np.pi / 2
            size_x = length if i % 2 == 0 else width
            size_z = width if i % 2 == 0 else length
            position_x = round((size_z / 2) * np.sin(rotation_y),3)
            position_z = round((size_z / 2) * np.cos(rotation_y),3)
            walls.append(
                    {
                    "category": "wall",
                    "material": wall_material,
                    "holes": [],
                    "rotation": [0, i * 90, 0],
                    "relative_pos": [position_x, position_z],
                    "size": [size_x, WALL_HEIGHT, WALL_WIDTH]
                }
            )
    
        return walls

    for floor in object_plans:
        for surface in floor["surfaces"]:
            
            length, width, center = PolygonConverter.bbox_dimensions(floor["bbox"])
            surface["xz"] = [-length/2, -width/2, length/2, width/2]
            floor.update(
                {
                    "position": [center[0], surface["y"], center[1]],
                    "size": [length, surface["y"]*2, width],
                    "rotation": [0, 0, 0],
                    "material": random.choice(FLOOR_MATERIAL),
                }
            )
            
            walls = get_wall_rotation_pos(length, width)

            if "children" not in surface:
                surface["children"] = []
            else:
                for wall in walls:
                    for child in surface["children"]:
                        if child["category"] == "wall" and child["relative_pos"] ==wall["relative_pos"]:
                            wall.update(child)
            surface["children"].extend(walls)
                    
    return object_plans
    
class ObjectGenerator:
    def __init__(self):
        pass

    def place_objects_recursively(self, receptacle, result_objects=[]):
        if "surfaces" in receptacle:
            receptacle = self.preprocess_receptacle(receptacle)
            surface = random.choice(receptacle["surfaces"])
            surface_rect = surface["xz"]
            rect_placer = RectPlacer(surface_rect)
            if "children" in surface:
                for child in surface["children"]:
                    prefab = child["prefab"] if "prefab" in child else None
                    object = Prefab.get_instance(child["category"], prefab)
                    object.update(child)
                    if "size" in object and object["size"]:
                        rotation = [x+y for x, y in zip(surface["direction"], receptacle["rotation"])]
                        if "rotation" not in object:
                            object["rotation"] = receptacle["rotation"]
                        for i in range(10): # try 10 times
                            object["position_xy"], object["position"] = self.get_object_pos(receptacle["position"], object, surface, rotation)
                            # get the rotation of the surface
                            object["bbox"] = PolygonConverter().get_bbox(object["position"], object["size"])
                            object["scale"] = [1, 1, 1]
                            if object["category"] in ["wall", "Door", "Window"]:
                                result_objects.append(object)
                                if object["category"] in ["Door", "Window"]:
                                    for item in result_objects:
                                        if item == receptacle:
                                            item["holes"].append({
                                                "position_xy":object["position_xy"],
                                                "size_xy": object["size"][:2],
                                                })
                                self.place_objects_recursively(object, result_objects)
                                break
                            else: 
                                if rect_placer.place_rectangle(object["prefab"], object["bbox"]):
                                    result_objects.append(object)
                                    self.place_objects_recursively(object, result_objects)
                                    break
        return result_objects

    def preprocess_receptacle(self, receptacle):
        """
        Preprocess the first receptacle, which should have initially provided the surface
        """
        if "category" not in receptacle:
            receptacle["category"] = Prefab.get_category(receptacle["prefab"])
            
        receptacle = PolygonConverter().get_surfaces(receptacle)
        return receptacle
    
    def get_object_pos(self, receptacle_pos, object, surface, rotation):
        """
        Set the object rotation the same as the receptacle
        """
        # find the absolute position of a point relative to a cuboid that has been rotated
        # get the position of the object relative to the surface
        object_to_surface_pos = PositionGenerator().get_position(object, surface)
        # get the position of the point relative to the center of the cuboid 
        surface_to_receptacle_pos = [0,surface["y"],0]
        object_to_receptacle_pos = [x+y for x, y in zip(object_to_surface_pos, surface_to_receptacle_pos)]

        # rotate the point using the given angles [angle_x, angle_y, angle_z]
        rotated_object_to_receptacle_pos = PolygonConverter.rotate_3D(object_to_receptacle_pos, rotation)

        # After applying the rotation, translate the rotated point back to its absolute position 
        object_position = [m + n for m, n in zip(receptacle_pos, rotated_object_to_receptacle_pos)]

        position_xy = object_to_surface_pos[0:3:2]
        return position_xy, object_position
    
def wall_postprocess(walls):
    """
    Remove walls that are duplicated
    """
    unique_vertices = []
    for wall in walls:
        wall_vertices = []
        if wall["position"] not in unique_vertices:
            unique_vertices.append(wall["position"])
        else:
            if "holes" not in wall:
                wall["holes"] = []
            
    return walls

if __name__ == "__main__":
    object_plans = load_json("legent/scene_generation/utils/metascene.json")
    scene = {}

    object_plans = generate_floor_walls(object_plans)

    all_objects = []
    for objects in object_plans:
        object_generator = ObjectGenerator()
        objects = object_generator.place_objects_recursively(objects, [])
        all_objects.extend(objects)

    scene["floors"] = object_plans

    scene["walls"] = []
    for object in all_objects:
        if object["category"] == "agent":
            scene["agent"] = object
        if object["category"] == "player":
            scene["player"] = object
        if object["category"] == "wall":
            scene["walls"].append(object)


    scene["instances"] = [object for object in all_objects if object["category"] not in ["wall", "agent", "floor", "player"]]
    
    scene = complete_scene(scene)
    # print(scene)
    scene_path = "legent/scene_generation/utils/scene.json"
    store_json(scene, scene_path)
    take_photo(scene_path, f"{os.getcwd()}/legent/scene_generation/utils/photo.png")

   