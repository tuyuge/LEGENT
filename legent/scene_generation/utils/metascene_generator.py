import os
import random
from legent.server.rect_placer import RectPlacer
from legent.scene_generation.utils.constants import FLOOR_MATERIAL, WALL_MATERIAL, WALL_HEIGHT, WALL_WIDTH, FLOOR_HEIGHT
from legent.scene_generation.utils.helper_functions import RectangleProcessor, InstanceGenerator, PolygonConverter, complete_scene, take_photo, play_with_scene, load_json
import copy

class PositionGenerator:
    def __init__(self):
        pass

    def _rotate_size(self, size, rotation):
        size = PolygonConverter().rotate_3D(size, rotation)
        return [abs(dim) for dim in size]
    
    def _rotate_bbox(self, bbox, rotation):
        length, width, _ = PolygonConverter.bbox_dimensions(bbox)
        new_surface_size = self._rotate_size([length,0,width], rotation)[0:3:2]
        bbox = PolygonConverter().get_bbox([0,0], new_surface_size)
        return bbox

    def _get_auto_position(self, surface, size, instance):
        x_min, z_min, x_max, z_max = surface
        x = random.uniform(x_min + size[0]/2, x_max - size[0]/2)
        z = random.uniform(z_min + size[2]/2, z_max - size[2]/2)
        x_auto_min = x_min + size[0]/2
        z_auto_min = z_min + size[2]/2
        # place at left and bottom if auto
        x, y, z = self._apply_instance_position(instance, x_auto_min, z_auto_min, [x, size[1]/2, z])
        return x, y, z

    def _apply_instance_position(self, instance, x_default, z_default, random_pos):
        x, y, z = random_pos
        if "position_xz" in instance:
            position_x, position_z = instance["position_xz"]
            if position_x == "auto":
                x = x_default
            elif isinstance(position_x, (int, float)):
                x = position_x
            if position_z == "auto":
                z = z_default
            elif isinstance(position_z, (int, float)):
                z = position_z
        return x, y, z
    
    def _get_position(self, instance, receptacle, surface):   
        """
        Get the position of the object relative to the surface
        """
        surface_bbox = surface["xz"]
        if receptacle["category"] == "wall":
            # rotate size according to surface direction
            size = self._rotate_size(instance["size"], surface["direction"])
            # get the relative pos
            relative_pos = self._get_auto_position(surface_bbox, size, instance)  
        else:
            # rotate the surface_bbox
            surface_bbox = self._rotate_bbox(surface_bbox, instance["rotation"])
            relative_pos = self._get_auto_position(surface_bbox, instance["size"], instance)  
            # need to rotate pos and size
            relative_pos = PolygonConverter.rotate_3D(relative_pos, instance["rotation"])
            size = self._rotate_size(instance["size"], instance["rotation"])

        size_xz = size[0:3:2]
        return relative_pos, size_xz

    def get_object_pos(self, receptacle, surface, object, rotation):
        """
        Get the position of the object relative to the surface and the absolute position
        """
        # find the absolute position of a point relative to a cuboid that has been rotated
        # get the position of the object relative to the surface
        # for debug, tell which instance to debug
        object_to_surface_pos, size_xz = self._get_position(object, receptacle, surface)
        # get the position of the point relative to the center of the cuboid 
        surface_to_receptacle_pos = [0,surface["y"],0]
        object_to_receptacle_pos = [x+y for x, y in zip(object_to_surface_pos, surface_to_receptacle_pos)]
        if object["category"] in ["door", "window"]:
            object_to_receptacle_pos[1] = 0
            
        # rotate the point using the given angles [angle_x, angle_y, angle_z]
        if object["category"] in ["door", "window"]:
            object_to_receptacle_pos = PolygonConverter.rotate_3D(object_to_receptacle_pos, [-rotation[0], rotation[1], rotation[2]])
        else:
            object_to_receptacle_pos = PolygonConverter.rotate_3D(object_to_receptacle_pos, rotation)
        # After applying the rotation, translate the rotated point back to its absolute position 
        object_position = [m + n for m, n in zip(receptacle["position"], object_to_receptacle_pos)]
        position_xz = object_to_surface_pos[0:3:2]
        return position_xz, size_xz, object_position

class LayoutGenerator:
    def __init__(self):
        # self.wall_material = random.choice(WALL_MATERIAL)
        self.wall_material = "#FFFFFF"
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
                "rotation": [0,0,0],
                # "material": random.choice(FLOOR_MATERIAL),
                "material": '#FFFFFF',
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
            # surface_rect = surface["xz"]
            # rect_placer = RectPlacer(surface_rect)
            if "children" in surface:
                for object in surface["children"]: 
                    if object["category"] == "bed":
                        pass 
                    # add door shadows to floor 
                    if "prefab" in object and object["prefab"] and "shadow" in object["prefab"]:
                        position_xz = [x-y for x, y in zip(object["position"][0:3:2], receptacle["position"][0:3:2])]
                        bbox = PolygonConverter(WALL_WIDTH).get_bbox(position_xz, object["size"][0:3:2])
                        # rect_placer.place_rectangle(object["prefab"], bbox)
                        continue

                    # set rotation as the receptacle rotation
                    if "angle" not in object:
                        object["rotation"] = receptacle["rotation"]
                    else:
                        object["rotation"] = [0, object["angle"], 0]


                    object = self.instance_generator.get_instance(object)
                    # only objects with size info will be placed
                    if "prefab" in object and object["prefab"] and "size" in object and object["size"]:
                        # get the total rotation of the surface
                        rotation = [x+y for x, y in zip(surface["direction"], receptacle["rotation"])]
                        
                        # if surface is not horizontal, the object is not affected by gravity
                        if receptacle["category"] in ["ceiling", "wall"]:
                            object["type"] = "kinematic"
                        
                        # relative position
                        # check collision, use relative position
                        object["position_xz"], size_xz, object["position"] = PositionGenerator().get_object_pos(receptacle, surface, object, rotation)
                        receptacle = self._postprocess_receptacle(receptacle, object, object["position_xz"], size_xz)
                        
                        object["bbox"] = PolygonConverter(WALL_WIDTH).get_bbox(object["position_xz"], size_xz)
                        
                        # if rect_placer.place_rectangle(object["prefab"], object["bbox"]):
                        if True:
                            if object["category"] == "window":
                                object["scale"] = [1,1,0.2]
                            self.final_instances.append(object)
                            print(f"Placed {object['category']} at {object['position_xz']} with bbox {object['bbox']}\n{'#'*30}\n")
                            self.place_objects_recursively(object)
                        else:
                            print(f"Failed to place {object['category']}: {object}\n{'#'*30}\n")
                    else:
                        print(f"Failed to place {object['category']}: {object}\n{'#'*30}\n")

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
        # if object is door or window, then add holes to wall
        hole_receptacles = ["door", "window"]
        if object["category"] in hole_receptacles and receptacle["category"] == "wall":
            receptacle.setdefault("holes", []).append({
                "position_xy": position_xz,
                "size_xy": size_xz
            })
        return receptacle
    

class SceneGenerator():
    def __init__(self, show_ceiling=False, door_collision=False, use_objaverse=False, use_holodeck=False):
        self.layout_generator = LayoutGenerator()
        self.object_generator = ObjectGenerator(InstanceGenerator(use_objaverse=use_objaverse, use_holodeck=use_holodeck))
        self.show_ceiling = show_ceiling
        self.door_collision = door_collision

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
        # first place wall objects
        walls = self._place_objects(walls)

        if self.door_collision:
            wall_objects = self.object_generator.final_instances
            shadows = self._convert_to_shadow(wall_objects)
        else:
            shadows = None
        floors = self._place_objects(floors, shadows=shadows)

        # then ceiling objects
        ceilings = self._place_objects(ceilings)
        # whether to show ceilings
        if self.show_ceiling:
            floors = floors + ceilings
        
        final_instances = self.object_generator.final_instances
        scene = {
            'floors': [self.clean_keys(item) for item in floors],
            'walls': [self.clean_keys(item) for item in walls],
            'instances': [self.clean_keys(obj) for obj in final_instances if obj['category'] not in ['agent', 'player', 'floor', 'ceiling', 'wall']],
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
    
    def _convert_to_shadow(self, wall_objects, door_shadow_length=0.5):
        """
        Add shadow to the object.
        """
        def create_shadow(obj, prefab, dim_index, pos_offset, shadow_length, swap_dims=False):
            """Helper function to create shadow for door based on orientation and position adjustments."""
            shadow = copy.deepcopy(obj)
            shadow["prefab"] = prefab
            shadow["position"][dim_index] += pos_offset
            if swap_dims:
                shadow["size"][0], shadow["size"][2] = shadow["size"][2], shadow_length
            else:
                shadow["size"][dim_index] = shadow_length
            return shadow

        shadow_objects = []
        for obj in wall_objects:
            if obj["category"] == "door":
                prefab = obj["prefab"] + "-shadow"
                shadow_length = door_shadow_length
                axis, pos_factor = (2, 1) if obj["rotation"][1] in [0, 180] else (0, 0)
                offsets = [WALL_WIDTH/2 + shadow_length/2, -WALL_WIDTH/2 - shadow_length/2]
                shadows = [create_shadow(obj, prefab, axis, offset, shadow_length, pos_factor == 0) for offset in offsets]
                shadow_objects.extend(shadows)
        print([self.clean_keys(obj) for obj in shadow_objects])
        return [self.clean_keys(obj) for obj in shadow_objects]


if __name__ == "__main__":
    scene_folder = f"{os.getcwd()}/legent/scenes"
    room_plans = load_json(f"{scene_folder}/metascene.json")
    # scene = SceneGenerator().generate_scene(room_plans)

    # # take a photo of the scene
    # take_photo(SceneGenerator(show_ceiling=True, door_collision=True, use_holodeck=True).generate_scene, room_plans, scene_folder, camera_field_of_view=120, camera_width=2048)
    take_photo(SceneGenerator(show_ceiling=False, door_collision=True, use_holodeck=True).generate_scene, room_plans, scene_folder, photo_type="topdown")
    # # play with the scene
    # scene = load_json("legent/scenes/metascene.json")
    # play_with_scene(f"{scene_folder}/scene.json", SceneGenerator(show_ceiling=False, door_collision=True, use_holodeck=True).generate_scene, scene, scene_folder)
