import os
import random
from legent.server.rect_placer import RectPlacer
from legent import store_json, load_json
from constants import FLOOR_MATERIAL, WALL_MATERIAL, WALL_HEIGHT, WALL_WIDTH, FLOOR_HEIGHT
from helper_functions import RectangleProcessor, InstanceGenerator, PolygonConverter, complete_scene, take_photo, play_with_scene


class LayoutGenerator:
    def __init__(self):
        self.wall_material = random.choice(WALL_MATERIAL)
        self.floors = []
        self.walls = []
        self.ceilings = []

    def _generate_floor(self, floor, floor_bbox, category="floor"):
        """
        Generate floor or ceiling
        """
        length, width, center = PolygonConverter.bbox_dimensions(floor_bbox)
        position_y = FLOOR_HEIGHT/2 if category == "floor" else WALL_HEIGHT

        floor.update(
            {
                "position": [center[0], position_y, center[1]],
                "size": [length, FLOOR_HEIGHT, width],
                "rotation": [0, 0, 0],
                "material": random.choice(FLOOR_MATERIAL),
                "category": category
            }
        )
        if category == "floor":
            x1_min, x2_min, x1_max, x2_max = floor["bbox"]
            room_vertices = [(x1_min, x2_min), (x1_max, x2_min), (x1_max, x2_max), (x1_min, x2_max)]
            floor["room_vertices"] = room_vertices
        return floor
    
    def _get_wall(self, wall_segment):
        """
        Get one wall
        """
        wall_vertices, wall_rotation, wall_length = wall_segment["vertices"], wall_segment["rotation"], wall_segment["length"]
        # get the midpoint of wall vertices
        position = [sum(x)/len(x) for x in zip(*wall_vertices)]
        position = [position[0], WALL_HEIGHT/2, position[1]]
        return {
                "material": self.wall_material,
                "rotation": [0, wall_rotation, 0],
                "position": position,
                "vertices": wall_vertices,
                "size": [wall_length, WALL_HEIGHT, WALL_WIDTH],
                "category": "wall"
            }

    def generate_layout(self, room_plans):
        """
        Generate floors, walls, and ceilings
        """
        rect_processor = RectangleProcessor()
        for room_plan in room_plans:
            # add floor
            floor = self._generate_floor(room_plan["floor"][0], room_plan["floor"][0]["bbox"], "floor")
            self.floors.append(floor)
            
            # add ceiling if exists
            if "ceiling" in room_plan:
                ceiling = self._generate_floor(room_plan["ceiling"][0], floor["bbox"], "ceiling")
                self.ceilings.append(ceiling)

            # add walls
            # first get provided walls
            if "walls" in room_plan:
                provided_walls = room_plan["walls"]
            # then get the wall segments for the room
            wall_segments = rect_processor.process_new_rectangle(floor["room_vertices"])
            for wall_segment in wall_segments:
                wall = self._get_wall(wall_segment)
                if "walls" in room_plan:
                    for provided_wall in provided_walls:
                        if provided_wall["angle"] == wall["rotation"][1]:
                            wall.update(provided_wall)
                            break
                self.walls.append(wall)
        return self.floors, self.walls, self.ceilings
    

class ObjectGenerator:
    def __init__(self, instance_generator):
        self.instance_generator = instance_generator
        self.final_instances = []

    def place_objects_recursively(self, receptacle):
        """
        Given an receptacle with children in surfaces, place objects and save into final_instances
        """
        if "surfaces" in receptacle:
            receptacle = self._preprocess_receptacle(receptacle)
            surface = random.choice(receptacle["surfaces"])
            surface_rect = surface["xz"]
            rect_placer = RectPlacer(surface_rect)
            if "children" in surface:
                for object in surface["children"]:
                    object = self.instance_generator.get_instance(object)
                    # only objects with size info will be placed
                    if "size" in object and object["size"]:
                        # set rotation as the receptacle rotation
                        if "rotation" not in object:
                            object["rotation"] = receptacle["rotation"]

                        # get the total rotation of the object
                        rotation = [x+y for x, y in zip(surface["direction"], receptacle["rotation"])]
                        
                        for i in range(10): # try 10 times
                            object["position_xy"], object["position"] = self._get_object_pos(receptacle, object, surface, rotation)
                            object["bbox"] = PolygonConverter(WALL_WIDTH).get_bbox(object["position"], object["size"])
                            object["scale"] = [1, 1, 1]

                            # if category in wall, door, window, directly place them without checking collision
                            if object["category"] in ["wall", "door", "window"]:
                                self.final_instances.append(object)
                                if object["category"] in ["door", "window"]:
                                    receptacle.setdefault("holes", []).append({
                                        "position_xy": object["position_xy"],
                                        "size_xy": object["size"][:2]
                                    })
                                self.place_objects_recursively(object)
                                break
                            else: 
                                # check collision
                                if rect_placer.place_rectangle(object["prefab"], object["bbox"]):
                                    self.final_instances.append(object)
                                    self.place_objects_recursively(object)
                                    break
        return receptacle

    def _preprocess_receptacle(self, receptacle):
        """
        Preprocess the first receptacle, which should have initially provided the surface
        """
        if "category" not in receptacle:
            receptacle["category"] = self.instance_generator._get_category(receptacle["prefab"])
            
        receptacle = PolygonConverter(WALL_WIDTH).get_surfaces(receptacle)
        return receptacle
    
    def _get_object_pos(self, receptacle, object, surface, rotation):
        """
        Get the position of the object relative to the surface and the absolute position
        """
        receptacle_category, receptacle_pos = receptacle["category"], receptacle["position"]
        # find the absolute position of a point relative to a cuboid that has been rotated
        # get the position of the object relative to the surface
        object_to_surface_pos = self._get_position(object, surface, receptacle_category)
        # get the position of the point relative to the center of the cuboid 
        if receptacle_category == "ceiling":
            surface["y"] = - surface["y"]
        surface_to_receptacle_pos = [0,surface["y"],0]
        object_to_receptacle_pos = [x+y for x, y in zip(object_to_surface_pos, surface_to_receptacle_pos)]
        # rotate the point using the given angles [angle_x, angle_y, angle_z]
        rotated_object_to_receptacle_pos = PolygonConverter.rotate_3D(object_to_receptacle_pos, rotation)
        # After applying the rotation, translate the rotated point back to its absolute position 
        object_position = [m + n for m, n in zip(receptacle_pos, rotated_object_to_receptacle_pos)]
        position_xy = object_to_surface_pos[0:3:2]
        return position_xy, object_position
    
    def _get_position(self, instance, surface, receptacle_category):   
        """
        Get the position of the object relative to the surface
        """
        category, size = instance["category"], instance["size"]
        # rotate the size according to the direction of the surface
        rotated_size = PolygonConverter().rotate_3D(size, surface["direction"])   
        abs_size = [abs(dim) for dim in rotated_size]
        y = - abs_size[1]/2 if receptacle_category == "ceiling" else abs_size[1]/2
        length, width, _ = PolygonConverter.bbox_dimensions(surface["xz"])

        # Initialize x and z with default random positioning within bounds
        x = random.uniform(-length / 2 + abs_size[0] / 2, length / 2 - abs_size[0] / 2)
        z = random.uniform(-width / 2 + abs_size[2] / 2, width / 2 - abs_size[2] / 2)
        
        # Override x and z if 'relative_pos' is available in instance
        if "relative_pos" in instance:
            relative_pos = instance["relative_pos"]
            if isinstance(relative_pos, list):
                x, z = relative_pos
            elif isinstance(relative_pos, (float, int)):  # Assumes it's a valid x position if single value
                x = relative_pos

        # Adjust position for doors and windows
        if category == "door":
            y = -WALL_WIDTH / 2
            z = abs_size[2] / 2 - width / 2
        elif category == "window":
            y = -WALL_WIDTH / 2

        return x, y, z
    
class SceneGenerator():
    def __init__(self, add_ceiling=False):
        self.layout_generator = LayoutGenerator()
        self.object_generator = ObjectGenerator(InstanceGenerator())
        self.add_ceiling = add_ceiling

    def _place_objects(self, receptacles):
        new_receptacles = []
        for receptacle in receptacles:
            receptacle = self.object_generator.place_objects_recursively(receptacle)
            new_receptacles.append(receptacle)
        return new_receptacles

    def generate_scene(self, room_plans):
        floors, walls, ceilings = self.layout_generator.generate_layout(room_plans)
        if self.add_ceiling:
            floors = floors + ceilings
        floors = self._place_objects(floors)
        walls = self._place_objects(walls)
        final_instances = self.object_generator.final_instances
        scene = {
            'floors': [self.clean_keys(item) for item in floors],
            'walls': [self.clean_keys(item) for item in walls],
            'instances': [self.clean_keys(obj) for obj in final_instances if obj['category'] not in ['agent', 'player']],
            'agent': next((self.clean_keys(obj) for obj in final_instances if obj['category'] == 'agent'), None),
            'player': next((self.clean_keys(obj) for obj in final_instances if obj['category'] == 'player'), None)
        }
        scene = complete_scene(scene)
        return scene
    
    def clean_keys(self, item):
        """
        Remain only the keys that are needed in the final scene
        """
        if item["category"] in ["floor", "ceiling", "wall"]:
            keys = ["position", "size", "rotation", "material", "holes", "bbox"]
        else:
            keys = ["prefab", "position", "rotation", "scale"]
        item = {k: item[k] for k in keys if k in item}
        return item
        
if __name__ == "__main__":
    scene_folder = f"{os.getcwd()}/legent/scenes"
    room_plans = load_json(f"{scene_folder}/metascene.json")

    # # take a photo of the scene
    take_photo(f"{scene_folder}/scene.json", SceneGenerator().generate_scene, room_plans, scene_folder)

    # play with the scene
    # play_with_scene(f"{scene_folder}/scene.json", SceneGenerator().generate_scene, room_plans, scene_folder)

   