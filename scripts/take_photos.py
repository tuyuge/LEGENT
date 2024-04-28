from legent import Environment, ResetInfo, load_json,generate_scene, TakePhotoWithVisiblityInfo, store_json
import os


scene_folder = f"{os.getcwd()}/legent/scenes"
os.makedirs(scene_folder, exist_ok=True)

env = Environment(env_path="auto", camera_resolution=1024, camera_field_of_view=120)

try:
    for i in range(1):
        absolute_path = f"{scene_folder}/{i:04d}.png"
        print(f"save photo of scene {i} to {absolute_path}")
        scene = load_json(f"{scene_folder}/scene.json")
        position = scene["player"]["position"].copy()
        position[1] += 1
        rotation = scene["player"]["rotation"]
        obs = env.reset(ResetInfo(scene, api_calls=[TakePhotoWithVisiblityInfo(absolute_path, position, rotation, width=4096, height=4096, vertical_field_of_view=90)]))

finally:
    env.close()
