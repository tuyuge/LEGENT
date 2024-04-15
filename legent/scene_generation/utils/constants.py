from legent import load_json, store_json
import pandas as pd

FLOOR_HEIGHT = 0.1
WALL_HEIGHT = 2.5
WALL_WIDTH = 0.2


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
    "WorldMaterialsFree_SimpleRedBricks",
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

if __name__ == "__main__":
    all_assets = load_json("data/addressables.json")
    type_to_names = load_json("data/object_type_to_names.json")
    final_dict = {}
    for type, names in type_to_names.items():
        for name in names:
            for prefab in all_assets['prefabs']:
                if prefab['name'] == name:
                    if type not in final_dict:
                        final_dict[type] = []
                    else:
                        final_dict[type].append(prefab)
    
    store_json(final_dict, "data/prefabs.json")