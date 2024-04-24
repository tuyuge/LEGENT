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

def object_category_to_names(asset_path, types_to_names_path):
    object_dict = {}
    for asset in load_json(asset_path):
        object_type = asset["category"]
        object_name = asset["uid"]
        if object_type in object_dict:
            object_dict[object_type].append(object_name)
        else:
            object_dict[object_type] = [object_name]
    store_json(object_dict, types_to_names_path)


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


if __name__ == "__main__":
    print("here")
    # process assets
    # asset_path = "legent/scene_generation/data/addressables.json"
    # types_to_names_path = "legent/scene_generation/data/object_type_to_names.json"
    # all_assets = load_json(asset_path)["prefabs"]
    
    # object_category_to_names_normal(all_assets, types_to_names_path)
    # type_to_names = load_json(types_to_names_path)

    # final_dict = {}
    # for type, names in type_to_names.items():
    #     for name in names:
    #         for prefab in all_assets:
    #             if prefab['name'] == name:
    #                 if type not in final_dict:
    #                     final_dict[type] = []
    #                 final_dict[type].append(prefab)
    
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

    # process objaverse assets
    # original_path = "/Users/a0001/THUNLP/embodied_ai/Holodeck-main/data/objaverse_holodeck/09_23_combine_scale/objaverse_holodeck_database.json"
    # save_path = "/Users/a0001/THUNLP/legent_new/LEGENT/legent/scene_generation/data/objaverse_addresables.json"
    # process_assets(original_path, save_path)

    # asset_path = "legent/scene_generation/data/objaverse_addresables.json"
    # # process_assets(original_path, asset_path)
    # types_to_names_path = "legent/scene_generation/data/objaverse_object_type_to_names.json"
    # object_category_to_names(asset_path, types_to_names_path)

    # # included_categories  = ["bed"]
    
   


    # input_path = "/Users/a0001/THUNLP/legent_new/LEGENT/legent/scene_generation/data/objaverse_object_type_to_names.json"
    # output_path = "/Users/a0001/THUNLP/legent_new/LEGENT/legent/scene_generation/data/filtered_objaverse_object_type_to_names.json"

    # included_categories  = ['cup', 'chair', 'table', 'shelves', 'toy', 'key', 'mug', 'laptop', 'poster', 'plant', 'bowl', 'bottle', 'shelf', 'coat hanger', 'pot', 'cushion', 'vase', 'teddy bear', 'radio', 'frame', 'bed', 'shoe', 'television set', 'desk', 'lamp', 'coffee table', 'pan (for cooking)', 'pitcher', 'armchair', 'bag', 'pan', 'ottoman', 'candle', 'couch', 'sofa', 'window', 'book', 'computer', 'clock', 'hardback book', 'bookcase', 'refrigerator', 'water jug', 'stool', 'toaster oven', 'camera', 'cellular telephone', 'phone', 'table lamp', 'dining table', 'sink', 'microwave', 'cabinet', 'jug', 'trash can', 'basket', 'telephone', 'painting', 'wall clock', 'towel rack', 'monitor (computer equipment)', 'picture', 'toaster', 'water bottle', 'scissors', 'apple', 'desk lamp', 'couch', 'bed', 'drawer', 'oven', 'refrigerator', 'washing machine', 'television', 'computer', 'telephone', 'shower', 'toilet', 'mirror', 'lamp', 'bookshelf', 'couch', 'rug', 'window', 'door', 'pillow', 'blanket', 'cabinet', 'wardrobe', 'dresser', 'wall art', 'curtains']

    # data = load_json(input_path)
    # final_data = {key: data[key] for key in included_categories if key in data}
    # filter size too
    # size[0], size[1], size[2]
    # store_json(final_data, output_path)
    
    
    

    # objaverse_addressables = load_json("/Users/a0001/THUNLP/legent_new/LEGENT/legent/scene_generation/data/objaverse_addresables.json")
    # final_dict = {}
    # for type, names in object_type_to_names.items():
    #     # if type in included_categories:
    #     for name in names:
    #         for prefab in objaverse_addressables:
    #             if prefab['name'] == name:
    #                 if type not in final_dict:
    #                     final_dict[type] = []
    #                 final_dict[type].append(prefab)
    
    # store_json(final_dict, "legent/scene_generation/data/objaverse_prefabs.json")


    # object_type_to_names = load_json("/Users/a0001/THUNLP/legent_new/LEGENT/legent/scene_generation/data/filtered_objaverse_object_type_to_names.json")
    # list_of_objects = list(object_type_to_names.values())
    # objaverse_addressables = load_json("/Users/a0001/THUNLP/legent_new/LEGENT/legent/scene_generation/data/objaverse_addresables.json")
    # for prefab in objaverse_addressables:
    #     print(prefab['name'])
    #     # if prefab['name'] in list_of_objects:
    #     #     print(prefab)
                   