import os
import time
import cv2
import matplotlib

print(matplotlib.get_backend())

matplotlib.use('TkAgg')
from matplotlib import pyplot as plt

plt.ion()


def display_new_images(path):
    initial_files = dict([(f, None) for f in os.listdir(path)])
    fig, ax = plt.subplots(1, 1)
    plt.show()
    while True:
        current_files = dict([(f, None) for f in os.listdir(path)])
        # print current_files
        added_files = [f for f in current_files if not f in initial_files]
        # print added_files
        if added_files:
            jpg_files = [file for file in added_files if '.jpg' in file]
            jpg_path = os.path.join(path, jpg_files[-1])
            display_image(jpg_path, fig, ax)
        initial_files = current_files
        time.sleep(2)


def find_new_images(path, earlier_files):
    current_files = dict([(f, None) for f in os.listdir(path)])
    return [f for f in current_files if not f in earlier_files]


def display_image(image_path, fig, ax):
    img = cv2.imread(image_path)
    ax.cla()
    ax.imshow(img)
    ax.set_title(os.path.split(image_path)[-1])
    fig.canvas.draw()


def find_latest_path():
    path = '/home/pmc/pmchome/pmc-turbo/ground/gse_receiver_data'
    files = os.listdir(path)
    files = sorted(files)
    latest_path = os.path.join(path, files[-1], 'images')
    print(latest_path)
    return latest_path


def main():
    path = find_latest_path()
    display_new_images(path)


if __name__ == "__main__":
    main()
