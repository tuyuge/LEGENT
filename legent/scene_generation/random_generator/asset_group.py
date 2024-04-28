from legent import load_json
import random
from shapely.geometry import box, Polygon

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
        chidlren = []
        if max_edges == 4:
            children.append({
                []
            })
            
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
