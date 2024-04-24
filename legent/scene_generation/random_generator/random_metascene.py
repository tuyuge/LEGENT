from legent.scene_generation.utils.helper_functions import InstanceGenerator, PolygonConverter, take_photo, play_with_scene
from legent import store_json, load_json
import random
from legent.server.rect_placer import RectPlacer
from legent.scene_generation.utils.constants import WALL_HEIGHT, WALL_WIDTH
from legent.scene_generation.utils.metascene_generator import SceneGenerator

receptacle_types = ["onFloor", "onObject", "onWall", "onCeiling"]


class BboxArranger:
    def __init__(self, inner_bbox, receptacle_type="onFloor"):
        self.inner_bbox = inner_bbox
        self.outer_bbox = inner_bbox
        self.inner_instances = []
        self.outer_instances = []
        self.receptacle_type = receptacle_type

    def fill_outer_bbox(self, instance_generator, max_num):
        """
        convert instance 1D center to 2D center
        """
        for i in range(4):
            angle = 90 * i
            length, width, _ = PolygonConverter.bbox_dimensions(self.inner_bbox)
            actural_length = length if i % 2 == 0 else width
            line_min, line_max = -actural_length/2, actural_length/2
            instances = instance_generator(line_max - line_min, receptacle_type=self.receptacle_type, max_num=max_num)
            instances, line_width = self.get_line_1D_pos(line_min, line_max, instances, angle)
            if i == 0:
                self.outer_bbox[1] -= (line_width + WALL_WIDTH)
            elif i == 1:
                self.outer_bbox[0] -= (line_width + WALL_WIDTH)
            elif i == 2:
                self.outer_bbox[3] += (line_width + WALL_WIDTH)
            else:
                self.outer_bbox[2] += (line_width + WALL_WIDTH)
            self.outer_instances.extend(instances)
        for instance in self.outer_instances:
            size = PolygonConverter().rotate_3D(size, [0, angle, 0])
            size = [abs(dim) for dim in size]
            instance["bbox"] = PolygonConverter().get_bbox(instance["position_xz"], [instance["size"]["x"], instance["size"]["z"]])
        keys = ["prefab","category", "position_xz", "size", "bbox", "angle"]
        self.outer_instances = [{key:obj[key] for key in keys} for obj in self.outer_instances]
    
    def fill_inner_bbox(self, instance_generator, max_num):
        """
        convert instance 1D center to 2D center
        """
        
        rect_placer = RectPlacer(self.inner_bbox)
        x_min, z_min, x_max, z_max = self.inner_bbox
        instances = instance_generator(self.inner_bbox[2] - self.inner_bbox[0], receptacle_type=self.receptacle_type, max_num=max_num)
        for instance in instances:
            size = instance["size"]
            size = [size["x"], size["y"], size["z"]]
            
            for i in range(10):
                x = random.uniform(x_min + size[0]/2, x_max - size[0]/2)
                z = random.uniform(z_min + size[2]/2, z_max - size[2]/2)
                instance["position_xz"] = [x, z]
                instance["prefab"] = instance["name"]
                bbox = PolygonConverter().get_bbox(instance["position_xz"], size[0:3:2])
                instance["bbox"] = bbox
                if rect_placer.place_rectangle(instance["prefab"], bbox):
                    self.inner_instances.append(instance)
                    break
        keys = ["prefab","category", "position_xz"]
        self.inner_instances = [{key:obj[key] for key in keys} for obj in self.inner_instances]
    
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
        category = random.choice(list(object_types_to_names.keys()))
        list_of_objects = prefabs[category]
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

    def generate_room_bbox(self):
        length = random.uniform(2, 3)
        width = random.uniform(2, 3) 
        bbox = [0, 0, length, width]
        return bbox

    def generate_floor_objects(self, room_bbox):
        bbox_arranger = BboxArranger(room_bbox)
        bbox_arranger.fill_outer_bbox(get_random_instances, max_num=5)
        # bbox_arranger.fill_inner_bbox(get_random_instances, max_num=1)
        return bbox_arranger.outer_instances, bbox_arranger.outer_bbox, bbox_arranger.inner_bbox
        
    def generate_wall_objects(self, window_num=1, door_num=1):
        walls = []
        walls.append({"angle":0, "surfaces":[{"children":[{"category":"door", "position_xz":["auto", "auto"]}]}]})
        walls.append({"angle":90, "surfaces":[{"children":[{"category":"window", "position_xz":[None, "auto"]}]}]})
        walls.append({"angle":180, "surfaces":[{"children":[{"category":"picture"}]}]})
        walls.append({"angle":270, "surfaces":[{"children":[{"category":"picture"}]}]})
        return walls
    
    def calculate_player_position(self, inner_bbox, outer_bbox):
        grid_type = random.choice(["inner", "outer"])
        if grid_type == "inner":
            bbox = inner_bbox
        elif grid_type == "outer":
            bbox = outer_bbox
            # change the z_max to the outer_bbox z_max
            bbox[3] = inner_bbox[1] # change z_max to inner bbox z_min

        x_min, z_min, x_max, z_max = bbox
        size = [0.5, 2, 0.5]
        x = random.uniform(x_min + size[0]/2, x_max - size[0]/2)
        z = random.uniform(z_min + size[2]/2, z_max - size[2]/2)
        return {
            "prefab": "player",
            "category": "player",
            "position_xz": [x, z],
            "size": size
        }
        

    def add_one_room(self):
        room = {
            "floor": [{"surfaces": [{}]}]
        }
        inner_bbox = self.generate_room_bbox()
        print("inner_bbox", inner_bbox)
        floor_objects, outer_bbox, inner_bbox = self.generate_floor_objects(inner_bbox)
        floor_objects.append({"category":"player"})
        print("outer_bbox", outer_bbox)

        room["floor"][0]["surfaces"][0]["children"], room["floor"][0]["bbox"] = floor_objects, outer_bbox
        room["walls"] = self.generate_wall_objects()
        room["ceiling"] = [{"surfaces": [{"children":[{"category":"light", "position_xz":[0, 0]}]}]}]
            
        self.scene.append(room)

if __name__ == "__main__":
    use_holodeck = True
    import os
    
    
    if use_holodeck:
        prefabs = load_json("legent/scene_generation/data/objaverse_prefabs.json")
        object_types_to_names = load_json("legent/scene_generation/data/filtered_objaverse_object_type_to_names.json")
    else:
        addresable = load_json("legent/scene_generation/data/addressables.json")["prefabs"]
        object_types_to_names = load_json("legent/scene_generation/data/object_type_to_names.json")


    scene = MetaSceneCreator().scene
    store_json(scene, "legent/scenes/metascene.json")


    # # # # take a photo of the scene
    # scene_folder = f"{os.getcwd()}/legent/scenes"
    # scene = load_json("legent/scenes/metascene.json")
    # # # take a photo of the scene
    # take_photo(SceneGenerator(show_ceiling=True, door_collision=True, use_holodeck=True).generate_scene, scene, scene_folder, camera_field_of_view=90,vertical_field_of_view=60, camera_width=2048)
    # # take_photo(SceneGenerator(show_ceiling=False, door_collision=True, use_holodeck=True).generate_scene, scene, scene_folder, photo_type="topdown")
    # # # play with the scene
    # # scene = load_json("legent/scenes/metascene.json")
    # play_with_scene(f"{scene_folder}/scene.json", SceneGenerator(show_ceiling=False, door_collision=True, use_holodeck=True).generate_scene, scene, scene_folder)
