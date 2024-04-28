from legent.scene_generation.utils.helper_functions import PolygonConverter, take_photo, play_with_scene
from legent import store_json, load_json
import random
from legent.server.rect_placer import RectPlacer
from legent.scene_generation.utils.constants import WALL_WIDTH
from legent.scene_generation.utils.metascene_generator import SceneGenerator
import numpy as np
from shapely.geometry import box, Polygon

receptacle_types = ["onFloor", "onObject", "onWall", "onCeiling"]


class AssetGroup:
    def __init__(self):
        self.asset_groups = load_json("legent/scene_generation/data/groups.json")
        self.types_to_instances = load_json("legent/scene_generation/data/object_type_to_instances.json")

    def get_random_group(self):
        random_group = random.choice(self.asset_groups)
        center_category, member_category, receptacle, max_edges, padding = random_group["center"], random_group["member"], random_group["receptacle"], random_group["max_edges"], random_group["padding"]
        
        center_asset = random.choice(self.types_to_instances(center_category))
        member_asset = random.choice(self.types_to_instances(member_category))

        center_obj = self.compute_group_info(center_asset, member_asset, max_edges, padding)

        return center_obj
    
    # add a surface to the center obj
    def compute_group_info(self, center_asset, member_asset, max_edges, padding):
        """
        group objects are objects placed at the four surfaces of the center obj
        """
        if max_edges == 4:
            for i in range(4):
                 children = [{"angle":i*90,"prefab": member_asset["prefab"]} for i in range(4)]
            
        size = self.compute_group_size(group)
        return center_obj
    

    def compute_group_size(self, rectangles):
        """
        Computes the bounding box for a group of rectangles.
        """
        boxes = [box(*rect) for rect in rectangles]
        union = boxes[0]
        for b in boxes[1:]:
            union = union.union(b)
        return union.bounds


class BboxArranger:
    def __init__(self, receptacle_type="onFloor"):
        self.bbox = self.get_random_bbox()
        self.instances = []
        self.receptacle_type = receptacle_type

    def fill_bbox(self, instance_generator, max_num):
        """
        convert instance 1D center to 2D center
        """
        for i in range(4):
            angle = 90 * i
            length, width, _ = PolygonConverter.bbox_dimensions(self.bbox)
            actural_length = length if i % 2 == 0 else width
            line_min, line_max = -actural_length/2, actural_length/2
            instances = instance_generator(line_max - line_min, receptacle_type=self.receptacle_type, max_num=max_num)
            instances, line_width = self.get_line_1D_pos(line_min, line_max, instances, angle)
            self.instances.extend(instances)
        keys = ["prefab","category", "position_xz", "angle"]
        self.instances = [{key:obj[key] for key in keys} for obj in self.instances]
    
    def get_random_bbox(self):
        length = random.uniform(3, 5)
        width = random.uniform(3, 5) 
        bbox = [-length/2, -width/2, length/2, width/2]
        return bbox
    
    def get_line_1D_pos(self, line_min, line_max, instances, angle):
        """
        Arrange objects in a line, the objects' total length is less than the length of the line
        """
        line_length = line_max - line_min
        instance_lengths = [instance['size']['x'] for instance in instances]
        remaining_length = line_length - sum(instance_lengths)

        starting_points = self.generate_floats(len(instances), remaining_length)
        starting_points.sort()  # Ensure the starting points are in order

        # Place each subline and calculate their positions and center points
        current_position = line_min
        for start_point, instance in zip(starting_points, instances):
            adjusted_start_point = current_position + start_point
            end_point = adjusted_start_point + instance['size']['x']
            center_point = (adjusted_start_point + end_point) / 2
            current_position = end_point
            instance["position_xz"] = [center_point, "auto"]
            instance["angle"] = angle
            instance["prefab"] = instance["name"]
            assert center_point >= line_min and center_point <= line_max
        line_width = max([instance['size']['z'] for instance in instances])
        return instances, line_width

    def generate_floats(self, n, max_value, random_gen=True):
        """
        Generate n random floats that sum up to less than max_value
        """
        if random_gen:
            # Generate n random numbers
            random_floats = [random.uniform(0, max_value) for _ in range(n)]
            total = sum(random_floats)
            if total < max_value:
                return random_floats
            else:
                # Scale the numbers to fit the max_value constraint
                scale = max_value / total
                scaled_floats = [x * scale for x in random_floats]
                epsilon = sum(scaled_floats) - max_value
                scaled_floats[0] -= epsilon  # Subtract the epsilon from the first number
                return scaled_floats
        else:
            return [max_value / n] * n

def get_random_instances(line_length, receptacle_type="onFloor", max_num=5):
    total_length = 0
    instances = []
    while True:
        # randomly select an object
        category = random.choice(list(OBJECT_TYPE_TO_INSTANCES.keys()))
        list_of_objects = OBJECT_TYPE_TO_INSTANCES[category]
        instance = random.choice(list_of_objects)
        
        if use_holodeck:
            receptacle_exclusion = [type for type in receptacle_types if type != receptacle_type]
            place = instance[receptacle_type] and instance["size"]["x"] < 2.2 and instance["size"]["z"] <= 2.2 and instance["size"]["y"] <= 2.2
            for item in receptacle_exclusion:
                if instance[item]:
                    place = False  
        else:
            place = True
        if place:
            size_x = instance["size"]["x"]
            total_length += size_x
            if total_length <= line_length:
                instances.append(instance)
            else:
                break
            if len(instances) >= max_num:
                break
    return instances

class MetaSceneCreator():
    def __init__(self, room_num=1):
        self.scene = []
        for i in range(room_num):
            self.add_one_room()
        
    def generate_wall_objects(self, window_num=1, door_num=1):
        walls = []
        walls.append({"angle":0, "surfaces":[{"children":[{"category":"door", "position_xz":[None, "auto"]}]}]})
        walls.append({"angle":90, "surfaces":[{"children":[{"category":"window", "position_xz":[None, 0]}]}]})
        walls.append({"angle":180, "surfaces":[{"children":[{"category":"picture"}]}]})
        walls.append({"angle":270, "surfaces":[{"children":[{"category":"picture"}]}]})
        return walls

    def add_one_room(self):
        room = {
            "floor": [{"surfaces": [{}]}]
        }

        bbox_arranger = BboxArranger()
        bbox_arranger.fill_bbox(get_random_instances, max_num=5)
        
        floor_objects = bbox_arranger.instances
        floor_objects.append({"category": "player", "prefab":"player"})
        room["floor"][0]["surfaces"][0]["children"], room["floor"][0]["bbox"] = floor_objects, bbox_arranger.bbox
        room["walls"] = self.generate_wall_objects()
        room["ceiling"] = [{"surfaces": [{"children":[{"category":"light", "position_xz":[0, 0]}]}]}]
            
        self.scene.append(room)

if __name__ == "__main__":
    use_holodeck = True
    import os
    scene_folder = f"{os.getcwd()}/legent/scenes"
   
    OBJECT_TYPE_TO_INSTANCES = load_json("legent/scene_generation/data/object_type_to_instances.json")

    room_plans = MetaSceneCreator().scene
    store_json(room_plans, "legent/scenes/metascene.json")

    scene = SceneGenerator(show_ceiling=False, door_collision=True).generate_scene(room_plans)
    store_json(scene, f"{scene_folder}/scene.json")
    take_photo(scene, scene_folder, photo_type="topdown")


    take_photo(scene, scene_folder)

    # scene = load_json(f"{scene_folder}/scene.json")
    # play_with_scene(scene)
  