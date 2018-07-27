import sys
sys.dont_write_bytecode = True

import numpy as np
from skimage.transform import downscale_local_mean
from skimage.transform import resize
import time
from PIL import Image


def pause():
    programPause = raw_input("Press the <ENTER> key to continue...")


def normalise_image(image):
    image = np.array(image)
    return (image - np.mean(image)) / np.std(image)

def unit_image(image):
    image  = np.array(image)
    max_along_dim = np.amax(image)
    return np.true_divide(image,max_along_dim)

def grayscale_img(image):
    return np.dot(image[...,:3], [0.299, 0.587, 0.114])

def process_image(rgb_image, crop=(None, None, None, None), downscaling_factor=(1, 1)):
    rgb_image = rgb_image[crop[0]:crop[1], crop[2]:crop[3], :]
    r, g, b = rgb_image[:, :, 0], rgb_image[:, :, 1], rgb_image[:, :, 2]
    gray = 0.2989 * r + 0.5870 * g + 0.1140 * b
    gray = gray[::2, ::2]
    gray = normalise_image(gray)
    return gray

def process_nature_atari(rgb_image, downscaling_dimension = (84, 84)):
    gray = grayscale_img(rgb_image)
    down_img = resize(gray, downscaling_dimension)
    down_img = unit_image(down_img)
    return down_img

def show(image):
    im = Image.fromarray(image)
    im.show()

def get_image_shape(env, crop, downscaling_factor):
    screen = env.reset()
    image = process_image(screen, crop, downscaling_factor)
    return np.shape(image)


class Timer:

    def __init__(self):
        self.clocks = {}

    def add_timer(self, name):
        self.clocks[name] = time.time()

    def get_timer(self, name):
        current_time = time.time()
        elapsed_time = current_time - self.clocks[name]
        self.clocks[name] = current_time
        return elapsed_time


def document_parameters(agent):
    # document parameters
    with open(agent.model_path + '/params.txt', 'w') as file:
        file.write('Environment: ' + str(agent.env) + '\n')
        file.write('Architecture: ' + str(agent.architecture) + '\n')
        file.write('Explore Rate: ' + str(agent.explore_rate) + '\n')
        file.write('Learning Rate: ' + str(agent.learning_rate) + '\n')
        file.write('Discount: ' + str(agent.discount) + '\n')
        file.write('Batch Size: ' + str(agent.replay_memory.batch_size) + '\n')
        file.write('Memory Capacity: ' + str(agent.replay_memory.memory_capacity) + '\n')
        file.write('Num Episodes: ' + str(agent.training_metadata.num_episodes) + '\n')
        file.write('Learning Rate Drop Frame Limit: ' + str(agent.training_metadata.frame_limit) + '\n')
