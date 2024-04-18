import os
import random
from legent.server.rect_placer import RectPlacer
from legent import load_json
from constants import FLOOR_MATERIAL, WALL_MATERIAL, WALL_HEIGHT, WALL_WIDTH, FLOOR_HEIGHT
from helper_functions import RectangleProcessor, InstanceGenerator, PolygonConverter, complete_scene, take_photo, play_with_scene, get_object_pos
import copy

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
        # make the floor and wall non-overlap
        position_y = 0 if category == "floor" else WALL_HEIGHT

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
                    # if "prefab" in object and object["prefab"] and "shadow" in object["prefab"]:
                    #     bbox = PolygonConverter(WALL_WIDTH).get_bbox(object["position"][0:3:2], object["size"][0:3:2])
                    #     rect_placer.place_rectangle(object["prefab"], bbox)
                    #     continue
                  
                    object = self.instance_generator.get_instance(object)
                    # only objects with size info will be placed
                    if "size" in object and object["size"]:
                        # set rotation as the receptacle rotation
                        if "angle" not in object:
                            object["rotation"] = receptacle["rotation"]
                        else:
                            object["rotation"] = [0, object["angle"], 0]

                        # add scale
                        object["scale"] = [1, 1, 1]
                        # get the total rotation of the object
                        rotation = [x+y for x, y in zip(surface["direction"], object["rotation"])]
                        
                        # if surface is not horizontal, the object is not affected by gravity
                        if surface["direction"] != [0, 20, 0]:
                            object["type"] = "kinematic"
                        
                        for i in range(10): # try 10 times
                            # relative position
                            object["position_xz"], size_xz, object["position"] = get_object_pos(receptacle, surface, object, rotation)
                            receptacle = self._postprocess_receptacle(receptacle, object, object["position_xz"], size_xz)

                            # check collision, use relative position
                            object["bbox"] = PolygonConverter(WALL_WIDTH).get_bbox(object["position_xz"], size_xz)
                            if rect_placer.place_rectangle(object["prefab"], object["bbox"]):
                                self.final_instances.append(object)
                                break
                        self.place_objects_recursively(object)
        return receptacle

    def _preprocess_receptacle(self, receptacle):
        """
        Preprocess the first receptacle, which should have initially provided the surface
        """
        if "category" not in receptacle:
            receptacle["category"] = self.instance_generator._get_category(receptacle["prefab"])
            
        receptacle = PolygonConverter(WALL_WIDTH).get_surfaces(receptacle)
        return receptacle
    
    def _postprocess_receptacle(self, receptacle, object, position_xz, size_xz):
        if object["category"] in ["door", "window"]:
            receptacle.setdefault("holes", []).append({
                "position_xy": position_xz,
                "size_xy": size_xz
            })
        return receptacle
    
class SceneGenerator():
    def __init__(self, add_ceiling=False):
        self.layout_generator = LayoutGenerator()
        self.object_generator = ObjectGenerator(InstanceGenerator())
        self.add_ceiling = add_ceiling

    def _place_objects(self, receptacles, shadows=None):
        new_receptacles = []
        for receptacle in receptacles:
            if shadows:
                receptacle["surfaces"][0]["children"] = shadows + receptacle["surfaces"][0]["children"]
            receptacle = self.object_generator.place_objects_recursively(receptacle)
            new_receptacles.append(receptacle)
        return new_receptacles

    def generate_scene(self, room_plans):
        floors, walls, ceilings = self.layout_generator.generate_layout(room_plans)
        if self.add_ceiling:
            floors = floors + ceilings
        
        # first place wall objects, then floor objects
        walls = self._place_objects(walls)
        # wall_objects = self.object_generator.final_instances
        # shadows = self._convert_to_shadow(wall_objects)
        floors = self._place_objects(floors)
        
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
            keys = ["prefab", "category", "position", "rotation", "scale", "type", "size", "bbox", "position_xz"]
        item = {k: item[k] for k in keys if k in item}
        return item
    
    # def _convert_to_shadow(self, wall_objects, door_shadow_length=0.5):
    #     """
    #     Add shadow to the object
    #     """
    #     shadow_objects = []
    #     for obj in wall_objects:
    #         obj["prefab"] = obj["prefab"]+"-shadow"
    #         if obj["category"] == "door":
    #             if obj["rotation"][1] in [0, 180]:
    #                 # deep copy a dict
    #                 door_shadow_1 = copy.deepcopy(obj)
    #                 door_shadow_1["position"][2] = obj["position"][2] + WALL_WIDTH/2 + door_shadow_length/2
    #                 door_shadow_1["size"][2] = door_shadow_length
    #                 shadow_objects.append(door_shadow_1)

    #                 door_shadow_2 = copy.deepcopy(obj)
    #                 door_shadow_2["position"][2] = obj["position"][2] - WALL_WIDTH/2 - door_shadow_length/2
    #                 door_shadow_2["size"][2] = door_shadow_length
    #                 shadow_objects.append(door_shadow_2)
                    
    #             else:
    #                 door_shadow_1 = copy.deepcopy(obj) 
    #                 door_shadow_1["position"][0] = obj["position"][0] + WALL_WIDTH/2 + door_shadow_length/2
    #                 size_x = door_shadow_1["size"][0]
    #                 door_shadow_1["size"][0] = door_shadow_length
    #                 door_shadow_1["size"][2] = size_x
    #                 shadow_objects.append(door_shadow_1)

    #                 door_shadow_2 = copy.deepcopy(obj)
    #                 door_shadow_2["position"][0] = obj["position"][0] - WALL_WIDTH/2 - door_shadow_length/2
    #                 size_x = door_shadow_2["size"][0]
    #                 door_shadow_2["size"][0] = door_shadow_length
    #                 door_shadow_2["size"][2] = size_x
    #                 shadow_objects.append(door_shadow_2)
    #     shadow_objects = [self.clean_keys(obj) for obj in shadow_objects]
    #     return shadow_objects

        
if __name__ == "__main__":
    scene_folder = f"{os.getcwd()}/legent/scenes"
    room_plans = load_json(f"{scene_folder}/metascene.json")
    # scene = SceneGenerator().generate_scene(room_plans)

    # # take a photo of the scene
    # take_photo(SceneGenerator(add_ceiling=False).generate_scene, room_plans, scene_folder)

    # play with the scene
    play_with_scene(f"{scene_folder}/scene.json", SceneGenerator().generate_scene, room_plans, scene_folder)

   