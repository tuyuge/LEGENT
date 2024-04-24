import objaverse
import objaverse.xl as oxl
import pandas as pd
import trimesh

from legent import Environment, Observation, generate_scene, ResetInfo
from legent.utils.config import ENV_FOLDER
import random

objaverse._VERSIONED_PATH = f"{ENV_FOLDER}/objaverse"


def objaverse_object(uid):
    objects = objaverse.load_objects([uid])
    return list(objects.values())[0]


def objaverse_object_info(uid, raw=False):
    annotation = objaverse.load_annotations([uid])[uid]
    if raw:
        return annotation
    info = {
        "uid": uid,
        "name": annotation["name"],
        "tags": [tag["name"] for tag in annotation["tags"]],
        "categories": [cat["name"] for cat in annotation["categories"]],
        "description": annotation["description"],
        "vertex_count": annotation["vertexCount"],
        "url": annotation["viewerUrl"],
    }
    return info


def try_objaverse():  # NOT annotated. The annotations are noisy.
    uids = objaverse.load_uids()

    # Sample some objects
    sample_uids = random.sample(uids, 5)
    for uid in sample_uids:
        info = objaverse_object_info(uid)
        print(info["name"], info)

    # Find the cherry-picked example shown in https://objaverse.allenai.org/objaverse-1.0
    # annotations = objaverse.load_annotations(uids)
    # uid = [uid for uid, annotation in annotations.items() if annotation["name"] == "Spicy Ramen Noodle"][0]
    uid = "101c08b5c8534944b43959b142a140b1"
    info = objaverse_object_info(uid)
    print(info["name"], info)

    # Download the model
    path = objaverse_object(uid)

    # Visualize the model
    trimesh.load(path).show()


def try_objaverse_lvis():  # Annotated with categories but much less objects
    # Get the information: 1156 categories, 46207 objects
    annotations = objaverse.load_lvis_annotations()
    # print(list(annotations.keys()))
    print("Categories:", len(annotations), "Objects:", sum([len(annotations[category]) for category in annotations]))

    # Sample a model from a category and print its information
    uids = annotations["Christmas_tree"]
    print("Christmas_tree Objects:", len(uids))
    uid = uids[0]  # random.choice(uids)
    info = objaverse_object_info(uid)
    print(info["name"], info)

    # Download the model
    path = objaverse_object(uid)

    # Visualize the model
    trimesh.load(path).show()


def try_objaverse_xl():  # NOT annotated. See https://huggingface.co/datasets/allenai/objaverse/discussions/7
    annotations: pd.DataFrame = oxl.get_annotations(download_dir=f"{ENV_FOLDER}/objaverse-xl")
    print(annotations)


# try_objaverse()
# try_objaverse_lvis()
# try_objaverse_xl()


def calculate_bounding_box_from_trimesh(file_path):
    mesh = trimesh.load(file_path)
    return mesh.bounds[0], mesh.bounds[1]


from legent import load_json

uid2size = load_json("uid2size.json")


def get_scale(uid, verbose=False):
    file_path = objaverse_object(uid)
    min_vals, max_vals = calculate_bounding_box_from_trimesh(file_path)
    mesh_size = max_vals - min_vals
    size = uid2size[uid]
    scale = size / mesh_size
    if verbose:
        return mesh_size, size, scale
    return scale


env = Environment(env_path=None, camera_resolution=1024, camera_field_of_view=120)

try:

    def build_scene_with_custom_objects():
        scene = generate_scene(room_num=1)

        # Download and use any object with gltf or glb format
        # For example, download the glb file and extract it from https://sketchfab.com/3d-models/lays-classic-hd-textures-free-download-d6cbb11c15ab4db4a100a4e694798279#download
        # The lays chips
        # scene["instances"].append({"prefab": "path/to/lays_classic__hd_textures__free_download.glb", "position": [1, 0.1, 1], "rotation": [90, 0, 0], "scale": [1, 1, 1], "type": "interactable"})

        # Use objects from objaverse
        # A slipper

        # from objaverse
        # 545ac531192944c0b97da2b7da0b636c

        # from holodeck
        # uid = "000a0c5cdc3146ea87485993fbaf5352"
        uid = random.choice(list(uid2size.keys()))
        scale = list(get_scale(uid))
        size = uid2size[uid]
        scene["instances"].append({"prefab": objaverse_object(uid), "position": [2, size[1] / 2, 2], "rotation": [0, 0, 0], "scale": scale, "type": "kinematic"})
        return scene

    obs: Observation = env.reset(ResetInfo(build_scene_with_custom_objects()))
    while True:
        if obs.text == "#RESET":
            scene = build_scene_with_custom_objects()
            env.reset(ResetInfo(scene))
        obs = env.step()
finally:
    env.close()
