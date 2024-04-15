from legent import load_json, Environment, ResetInfo, SaveTopDownView
import random

######## legent related ########
def take_photo(scene_path, photo_path):
    """
    Take a photo of the scene and save it to the abosulte path!
    """
    env = Environment(env_path="auto", camera_resolution=1024, camera_field_of_view=120)

    try:
        obs = env.reset(ResetInfo(scene=load_json(scene_path), api_calls=[SaveTopDownView(absolute_path=photo_path)]))
        print("Scene saved successfully: ", photo_path)
    finally:
        env.close()

def complete_scene(predefined_scene):
    """
    Complete a predefined scene by adding player, agent, interactable information etc.
    """
    # Helper function to get the center of the scene

    position = [100, 0.1, 100] 
    rotation = [0, random.randint(0, 360), 0]
    player = {
        "prefab": "",
        "position": position,
        "rotation": rotation,
        "scale": [1, 1, 1],
        "parent": -1,
        "type": ""
    }

    position = [1.5, 0.1, 1.5]
    rotation = [0, random.randint(0, 360), 0]
    agent = {
        "prefab": "",
        "position": position,
        "rotation": rotation,
        "scale": [1, 1, 1],
        "parent": -1,
        "type": ""
    }

    infos = {
        "prompt": "",
        "floors": predefined_scene["floors"] if "floors" in predefined_scene else [],
        "walls": predefined_scene["walls"] if "walls" in predefined_scene else [],
        "instances": predefined_scene["instances"] if "instances" in predefined_scene else [],
        "player": predefined_scene["player"] if "player" in predefined_scene else player,
        "agent": predefined_scene["agent"] if "agent" in predefined_scene else agent,
        "center": predefined_scene["center"] if "center" in predefined_scene else [4,10,2],
    }
    return infos
        