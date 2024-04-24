import multiprocessing
from legent import Environment, Action, ResetInfo, save_image, time_string, Observation, store_json, SaveTopDownView, TakePhotoWithVisiblityInfo
import os
import time
from datetime import timedelta
from legent.scene_generation.random_generator.random_metascene import SceneGenerator


# def take_topdown_photo(scene, scene_folder, env):
#     photo_path = f"{scene_folder}/topdown.png"
#     obs = env.reset(ResetInfo(scene, api_calls=[SaveTopDownView(absolute_path=photo_path)]))


# def take_fix_place_multiple_photos(scene, scene_folder, env):
#     obs: Observation = env.reset(ResetInfo(scene))

#     for j in range(4):
#         action = Action()
#         action.rotate_right = 90                
        
#         save_image(obs.image, f"{scene_folder}/agent_view{j}.png")
#         obs = env.step(action)

def take_fix_place_one_photo(scene, scene_folder, env):
    obs: Observation = env.reset(ResetInfo(scene))
    save_image(obs.image, f"{scene_folder}/agent_view.png")

# now we use this
def take_large_photo(scene, scene_folder, env):
    absolute_path = f"{scene_folder}/agent_view.png"
    position = scene["agent"]["position"].copy()
    position[1] += 1
    rotation = scene["agent"]["rotation"]
    # move agent away
    scene["agent"]["position"] = [100,0.1,100]
    obs = env.reset(ResetInfo(scene, api_calls=[TakePhotoWithVisiblityInfo(absolute_path, position, rotation, width=4096, height=2304, vertical_field_of_view=90)]))

    visible_objects = [scene["instances"][object_id] for object_id in obs.api_returns["objects_in_view"]]
    store_json(visible_objects, f"{scene_folder}/visible_objects.json")

def worker(worker_id, save_folder, scene_num):
    print(f"Worker {worker_id} started")
        
    env = Environment(env_path="auto", use_animation=False, camera_resolution=1024, camera_field_of_view=160, run_options={"port": 50100 + worker_id})

    try:
        for i in range(scene_num):
            # generate a scene
            scene = SceneGenerator.generate_scene()
            
            # save the scene to json
            current_scene_folder = f"{save_folder}/{time_string()}"
            os.makedirs(current_scene_folder, exist_ok=True)
            store_json(scene, f"{current_scene_folder}/scene.json")
            # take a topdown photo for every scene
            take_large_photo(scene, current_scene_folder, env)
            # take_fix_place_multiple_photos(scene, current_scene_folder, env)
            # take_topdown_photo(scene, current_scene_folder, env)

            print(f'Worker {worker_id}: Complete {i}th scene. Saved into {current_scene_folder}')
    except Exception as e:
        print(e)
    finally:
        env.close()
    print(f"Worker {worker_id} finished")


if __name__ == "__main__":
    # TODO change the number of processes and total_scene_num
    num_processes = 10
    print(f"Number of processes: {num_processes}")
    total_scene_num = 10
    scene_num = total_scene_num // num_processes

    start_time = time.time()

    # Create and start multiple processes
    # TODO change the save_root_folder to the desired path
    # save_root_folder = f"/data/public/tyg/train_data/{time_string()}"


    save_root_folder = f"/Users/a0001/THUNLP/legent_new/LEGENT/data/multi_view_90_160_0423_mixed"
    os.makedirs(save_root_folder, exist_ok=True)

    processes = []
    for i in range(num_processes):
        # TODO change the last argument to "fix_place_multiple" to take photos from different angles
        p = multiprocessing.Process(target=worker, args=(i, save_root_folder, scene_num))
        processes.append(p)

    for p in processes:
        p.start()

    # Wait for all processes to finish
    for p in processes:
        p.join()

    elapsed_time = timedelta(seconds=time.time() - start_time)
    print(f"Program finished in {elapsed_time}")