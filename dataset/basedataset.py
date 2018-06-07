import os
import sys
import time
import numpy as np

from abc import ABCMeta, abstractmethod
from keras.utils import to_categorical


class BaseDataset(object, metaclass=ABCMeta):

    def __init__(self, config):
        
        self.config = config

        self.shuffle_train = self.config.get('shuffle_train', True)
        self.shuffle_test = self.config.get('shuffle_test', False)
        self.batch_size = self.config.get('batch_size', 16)


    def iter_train_images_supervised(self):
        index = np.arange(self.x_train_l.shape[0])

        if self.shuffle_train:
            np.random.shuffle(index)

        for i in range(int(self.x_train_l.shape[0] / self.batch_size)):
            batch_x = self.x_train_l[index[i*self.batch_size:(i+1)*self.batch_size], :]
            batch_y = self.y_train_l[index[i*self.batch_size:(i+1)*self.batch_size]]

            if 'input_shape' in self.config:
                batch_x = batch_x.reshape([self.batch_size,] + self.config['input_shape'])
            batch_y = to_categorical(batch_y, num_classes=self.nb_classes)

            yield i, batch_x, batch_y


    def iter_train_images_unsupervised(self):
        index = np.arange(self.x_train_u.shape[0])

        if self.shuffle_train:
            np.random.shuffle(index)

        for i in range(int(self.x_train_u.shape[0] / self.batch_size)):
            batch_x = self.x_train_u[index[i*self.batch_size:(i+1)*self.batch_size], :]

            if 'input_shape' in self.config:
                batch_x = batch_x.reshape([self.batch_size,] + self.config['input_shape'])

            yield i, batch_x


    def iter_test_images(self):

        index = np.arange(self.x_test.shape[0])

        if self.shuffle_train:
            np.random.shuffle(index)

        for i in range(int(self.x_test.shape[0] / self.batch_size)):
            batch_x = self.x_test[index[i*self.batch_size:(i+1)*self.batch_size], :]
            batch_y = self.y_test[index[i*self.batch_size:(i+1)*self.batch_size]]

            if 'input_shape' in self.config:
                batch_x = batch_x.reshape([self.batch_size,] + self.config['input_shape'])
            
            yield i, batch_x, batch_y
