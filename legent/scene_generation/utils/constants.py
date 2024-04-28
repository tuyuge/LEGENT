from legent import load_json, store_json
import pandas as pd
from legent.scene_generation.utils.helper_functions import InstanceGenerator

FLOOR_HEIGHT = WALL_WIDTH = 0.05
WALL_HEIGHT = 3

FLOOR_MATERIAL = [
    'WorldMaterialsFree_HexBricks', 
    'WorldMaterialsFree_SimpleRedBricks', 
    'WorldMaterialsFree_BathroomTiles', 
    'WorldMaterialsFree_DryRockyDirt', 
    'WorldMaterialsFree_ClumpMud'
]


WALL_MATERIAL = [
    "#A3ABC3", 
    "#AB9E90", 
    "E0DFE3",
    "WorldMaterialsFree_AgedDarkWood",
    "WorldMaterialsFree_BasketWeaveBricks",
    "WorldMaterialsFree_BathroomTiles",
    "WorldMaterialsFree_BrushedIron",
    "WorldMaterialsFree_ClumpMud",
    "WorldMaterialsFree_CoarseConcrete",
    "WorldMaterialsFree_DesertCliffRock",
    "WorldMaterialsFree_DesertSandBrick",
    "WorldMaterialsFree_DryRockyDirt",
    "WorldMaterialsFree_GrassClumps",
    "WorldMaterialsFree_GrassGravel",
    "WorldMaterialsFree_HexBricks",
    "WorldMaterialsFree_PebbledGravel",
    "WorldMaterialsFree_PlainWhiteFabric",
    "WorldMaterialsFree_RuinStoneBricks",
    "WorldMaterialsFree_WavySand",
    "WorldMaterialsFree_WoodenFlooring",
]

# EDGE_PREFABS = load_json("data/prefabs.json")
# MIDDLE_PREFABS = load_json("data/middle_prefabs.json")


INCLUDED_CATEGORIES  = ['cup', 'chair', 'table', 'shelves', 'toy', 'key', 'mug', 'laptop', 'poster', 
                        'plant', 'bowl', 'bottle', 'shelf', 'coat hanger', 'pot', 'cushion', 'vase', 
                        'teddy bear', 'radio', 'frame', 'bed', 'shoe', 'television set', 'desk', 'lamp', 
                        'coffee table', 'pan (for cooking)', 'pitcher', 'armchair', 'bag', 'pan', 'ottoman', 
                        'candle', 'couch', 'sofa', 'window', 'book', 'computer', 'clock', 'hardback book', 'bookcase', 
                        'refrigerator', 'water jug', 'stool', 'toaster oven', 'camera', 'cellular telephone', 'phone', 
                        'table lamp', 'dining table', 'sink', 'microwave', 'cabinet', 'jug', 'trash can', 'basket', 
                        'telephone', 'painting', 'wall clock', 'towel rack', 'monitor (computer equipment)', 
                        'picture', 'toaster', 'water bottle', 'scissors', 'apple', 'desk lamp', 'couch', 'bed', 
                        'drawer', 'oven', 'refrigerator', 'washing machine', 'television', 'computer', 'telephone', 
                        'shower', 'toilet', 'mirror', 'lamp', 'bookshelf', 'couch', 'rug', 'window', 'door', 'pillow', 
                        'blanket', 'cabinet', 'wardrobe', 'dresser', 'wall art', 'curtains', 'light']



def get_edge_middle_prefabs():
    asset_dict = load_json("data/addressables.json")

    path = "data/placement_annotations_latest.csv"
    placement_annotations = pd.read_csv(path)

    edge_object_list = placement_annotations[
    (placement_annotations["onEdge"] == True) & 
    ((placement_annotations["inLivingRooms"] > 0) | 
     (placement_annotations["inBathrooms"] > 0) | 
     (placement_annotations["inBedrooms"] > 0) | 
     (placement_annotations["inKitchens"] > 0)) & 
    (placement_annotations["isPickupable"] == False)
    ]["Object"].to_list()

    middle_object_list = placement_annotations[
        (placement_annotations["inMiddle"] == True) & 
        ((placement_annotations["inLivingRooms"] > 0) | 
        (placement_annotations["inBathrooms"] > 0) | 
        (placement_annotations["inBedrooms"] > 0) | 
        (placement_annotations["inKitchens"] > 0)) & 
        (placement_annotations["isPickupable"] == False)
    ]["Object"].to_list()


    object_json_path = f"data/object_type_to_names.json"
    object_type_to_names = load_json(object_json_path)

    EDGE_PREFABS = []
    MIDDLE_PREFABS = []
    for obj_type, names in object_type_to_names.items():
        if obj_type.lower() in edge_object_list:
            for name in names:
                 for prefab in asset_dict['prefabs']:
                    if prefab['name'] == name:
                        area = prefab['size']["x"] * prefab['size']["z"]
                        if area > 0.1:
                            EDGE_PREFABS.append(prefab)
                            print(obj_type)


        if obj_type.lower() in middle_object_list:
            for name in names:
                 for prefab in asset_dict['prefabs']:
                    if prefab['name'] == name:
                        area = prefab['size']["x"] * prefab['size']["z"]
                        if area > 0.1:
                            MIDDLE_PREFABS.append(prefab)
                            print(obj_type)

    store_json(EDGE_PREFABS, "data/prefabs.json")
    store_json(MIDDLE_PREFABS, "data/middle_prefabs.json")


def process_assets(original_path, save_path):
    original_assets = load_json(original_path)
    save_assets = []
    for key, value in original_assets.items():
        annotations = value["annotations"]
        if annotations["size_annotated_by"] and annotations["size_annotated_by"].startswith("gpt"):
            pass
        else:
            continue
        try:
            type = value["objectMetadata"]["type"]
        except KeyError:
            type = None

        try:
            name = value["objectMetadata"]["name"]
        except KeyError:
            name = None
        size = value["objectMetadata"]["axisAlignedBoundingBox"]["size"]

        description= annotations["description"] if annotations["description"] else annotations["description_auto"]
        
        try:
            save_assets.append({
                "uid": annotations["uid"],
                "name": name,
                "category": annotations["category"],
                "size": size,
                "type": type,
                "description": description,
                "onFloor": annotations["onFloor"],
                "onObject": annotations["onObject"],
                "onWall": annotations["onWall"],
                "onCeiling": annotations["onCeiling"]
            })
        except KeyError as e:
            print("Wrong due to ", e)
            print(f"{annotations['uid']}")


    store_json(save_assets, save_path)



def object_category_to_names_normal(all_assets, types_to_names_path):
    object_dict = {}
    for asset in all_assets:
        object_name = asset["name"]
        object_type = InstanceGenerator.get_category(object_name)
        if object_type in object_dict:
            object_dict[object_type].append(object_name)
        else:
            object_dict[object_type] = [object_name]
    store_json(object_dict, types_to_names_path)


def get_prefab_to_asset_json():
    """
    in the form of prefab:{asset}
    """
    asset_list = load_json("legent/scene_generation/backup_data/objaverse_addresables.json")
    save_path = f"legent/scene_generation/data/prefab_to_asset.json"
    final_dict = {}
    for item in asset_list:
        final_dict[item["name"]] = item
    store_json(final_dict, save_path)


def get_object_type_to_instances_json():
    """
    in the form of category:[assets]
    """
    asset_path = "legent/scene_generation/backup_data/objaverse_addresables.json"
    types_to_instances_path = "legent/scene_generation/data/object_type_to_instances.json"
    types_to_instances = {}
    for asset in load_json(asset_path):
        object_size = asset["size"]
        object_type = asset["category"]
        if object_type in INCLUDED_CATEGORIES and object_size["x"] <2.3 and object_size["y"] < 2.3 and object_size["z"] < 2.3:
            if object_type == "picture":
                if object_size["z"] > 0.05:
                    continue
            if object_type == "door":
                if object_size["y"] < 2:
                    continue
                if object_size["x"] < 0.5 or object_size["x"] > 1.3:
                    continue
                if object_size["z"] > 0.3:
                    continue
            if object_type == "light":
                if object_size["y"] > 0.5:
                    continue
            if object_type in types_to_instances:
                types_to_instances[object_type].append(asset)
            else:
                types_to_instances[object_type] = [asset]
    store_json(types_to_instances, types_to_instances_path)


if __name__ == "__main__":
    # get_prefab_to_asset_json()
    get_object_type_to_instances_json()
    
    # final_dict.update({
    #     "agent":[
    #         {
    #             "name":"agent",
    #             "size": {
    #                 "x": 0.5,
    #                 "y": 1.8,
    #                 "z": 0.5
    #             }
    #         }
    #     ],
    #     "player":[
    #         {
    #             "name": "player",
    #             "size": {
    #                 "x": 0.5,
    #                 "y": 1.8,
    #                 "z": 0.5
    #             }
    #         }
    #     ],
    # })
    # store_json(final_dict, "legent/scene_generation/data/prefabs.json")

                   