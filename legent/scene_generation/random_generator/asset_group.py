from legent import load_json
import random
from shapely.geometry import box, Polygon

class AssetGroup:
    def __init__(self):
        self.asset_groups = load_json("legent/scene_generation/data/groups.json")
        self.types_to_names = load_json("legent/scene_generation/data/objaverse_object_type_to_names.json")
        self.addressables = load_json("legent/scene_generation/data/objaverse_addressables.json")

    def get_random_group(self):
        random_group = random.choice(self.asset_groups)
        center_category, member_category, receptacle, max_edges, padding = random_group["center"], random_group["member"], random_group["group"], random_group["member"]
        center_prefab = random.choice(self.types_to_names(center_category))
        member_prefab = random.choice(self.types_to_names(member_category))

        center_obj = self.compute_group_info(center_prefab, member_prefab)

        return center_obj
    
    # add a surface to the center obj
    def compute_group_info(self, group):
        """
        group objects are objects placed at the four surfaces of the center obj
        """
        
        center_obj_prefab = self.types_to_names(center_obj)
        center_obj_instance = self.addressables[center_obj_prefab]

        size = self.compute_group_size(group)
        member_prefab = self.types_to_names(group["member"])
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
