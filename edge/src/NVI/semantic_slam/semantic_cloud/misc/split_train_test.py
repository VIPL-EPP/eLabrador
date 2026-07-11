#!/usr/bin/env python
from shutil import copy
import subprocess
import os
def split():
    dataset_root = os.environ.get('NVI_DATASET_ROOT', 'data')
    root = os.path.join(dataset_root, 'SUNRGBD') + os.sep
    label_src = os.path.join(dataset_root, 'sunrgbd_train_test_labels') + os.sep
    train_src = os.path.join(dataset_root, 'SUNRGBD-train_images') + os.sep
    test_src = os.path.join(dataset_root, 'SUNRGBD-test_images') + os.sep

    # clear folders
    print('Clearing folders...')
    subprocess.Popen('rm '+root + 'test/*', shell=True).wait()
    subprocess.Popen('rm '+root + 'train/*', shell=True).wait()
    subprocess.Popen('rm '+root + 'annotations/test/*', shell=True).wait()
    subprocess.Popen('rm '+root + 'annotations/train/*', shell=True).wait()

    #test
    size_train = 5285#5285
    size_test = 5050#5050
    for i in range(1, 1+size_test):
        src = test_src+ 'img-%06d.jpg' % i
        dst = root + 'test'
        copy(src, dst)
        print('copying ' + src + ' to '+ dst)
    #train
    for i in range(1, 1+size_train):
        src = train_src+ 'img-%06d.jpg' % i
        dst = root + 'train'
        copy(src, dst)
        print('copying ' + src + ' to '+ dst)

    # val test
    for i in range(1, 1+size_test): #range(1, 5051)
        src = label_src+ 'img-%06d.png' % i
        dst = root+'annotations/test'
        copy(src, dst)
        print('copying ' + src + ' to '+ dst)
    # val train
    for i in range(5051, 5051+size_train): #range(5051, 10336)
        src = label_src+ 'img-%06d.png' % i
        dst = root+'annotations/train'
        copy(src, dst)
        print('copying ' + src + ' to '+ dst)

if __name__ == '__main__':
    split()
