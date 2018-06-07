# -*- coding: utf-8 -*-
# MIT License
# 
# Copyright (c) 2018 ZhicongYan
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# ==============================================================================



import os
import sys
import queue
import threading
import numpy as np

sys.path.append('.')
sys.path.append('../')

import tensorflow as tf
from keras.utils import to_categorical

from validator.validator import get_validator

class SupervisedTrainer(object):
	def __init__(self, config):
		self.config = config

		self.summary_dir = os.path.join(self.config['assets dir'], self.config.get('summary dir', 'log'))
		self.checkpoint_dir = os.path.join(self.config['assets dir'], self.config.get('checkpoint dir', 'checkpoint'))

		if not os.path.exists(self.summary_dir):
			os.mkdir(self.summary_dir)
		if not os.path.exists(self.checkpoint_dir):
			os.mkdir(self.checkpoint_dir)

		self.summary_steps = int(self.config.get('summary steps', 0))
		self.log_steps = int(self.config.get('log steps', 0))
		self.save_steps = int(self.config.get('save checkpoint steps', 0))
		
		self.multi_thread = self.config.get('multi thread', False)
		if self.multi_thread:
			self.batch_size = int(self.config.get('batch_size', 8))
			self.train_data_queue = queue.Queue(maxsize=5)
			self.train_data_inner_queue = queue.Queue(maxsize = self.batch_size * 3)

		self.validator_list = []
		for validator_config in self.config.get('validators', []):
			
			validator_params = validator_config.get('validator params', {})
			validator_params['assets dir'] = self.config['assets dir']

			validator = get_validator(validator_config['validator'], validator_params)
			validator_steps = int(validator_config['validate steps'])
			self.validator_list.append((validator_steps, validator))


	def read_data_inner_loop(self, coord, dataset, indices, t_ind, nb_threads):
		'''
			a inner read data loop thread, only be create or joined by read_data_loop.
			read data and put into self.train_data_inner_queue in loop
		'''
		for i, ind in enumerate(indices):
			if not coord.should_stop():
				if i % nb_threads == t_ind:
					img, label = dataset.read_train_image_by_index(ind)
					if img is not None:
						self.train_data_inner_queue.put((img, label))
			else:
				break

	def read_data_loop(self, coord, dataset, nb_threads=4):
		'''

		'''
		self.epoch = 0
		while not coord.should_stop():
			indices = dataset.get_train_indices()
			threads = [threading.Thread(target=self.read_data_inner_loop, 
								args=(coord, dataset, indices, t_ind, nb_threads)) for t_ind in range(nb_threads)]
			for t in threads:
				t.start()
			coord.join(threads)
			self.epoch += 1


	def read_data_transport_loop(self, coord):
		'''
		'''
		batch_x = []
		batch_y = []
		while not coord.should_stop():
			img, label = self.train_data_inner_queue.get()
			batch_x.append(img)
			batch_y.append(label)
			if len(batch_x) == self.batch_size:
				batch_x = np.array(batch_x)
				batch_y = np.array(batch_y)
				self.train_data_queue.put((self.epoch, batch_x, batch_y))
				batch_x = []
				batch_y = []
		while not self.train_data_inner_queue.empty():
			img, label = self.train_data_inner_queue.get()


	def train_inner(self, epoch, batch_x, batch_y, sess, model, dataset):
		'''
			the inner function for train a batch of images,
			input :
				epoch, batch_x, batch_y : train batch,
				sess : tensorflow run time Session
				model : 
				dataset :
			return :
				the current train step
		'''

		step, lr, loss, summary = model.train_on_batch_supervised(sess, batch_x, batch_y)
		
		if summary:
			self.summary_writer.add_summary(summary, step-1)

		if self.log_steps != 0 and step % self.log_steps == 1:
			print("epoch : %d, step : %d, lr : %f, loss : %f"%(epoch, step-1, lr, loss))

		if self.summary_steps != 0 and step % self.summary_steps == 1:
			summary = model.summary(sess)
			if summary:
				self.summary_writer.add_summary(summary, step-1)

		if self.save_steps != 0 and step % self.save_steps == 1:
			model.checkpoint_save(sess, self.checkpoint_dir, step-1)

		for validator_steps, validator in self.validator_list:
			if validator_steps != 0 and step % validator_steps == 1:
				validator.validate(model, dataset, sess, step-1)

		return step
	


	def train(self, sess, dataset, model):

		self.summary_writer = tf.summary.FileWriter(self.summary_dir, sess.graph)
		sess.run(tf.global_variables_initializer())

		# if in multi thread model, start threads for read data
		if self.multi_thread:
			self.coord = tf.train.Coordinator()
			threads = [threading.Thread(target=self.read_data_loop, args=(self.coord, dataset)),
						threading.Thread(target=self.read_data_transport_loop, args=(self.coord, ))]
			for t in threads:
				t.start()

		if self.config.get('continue train', False):
			if model.checkpoint_load(sess, self.checkpoint_dir):
				print("Continue Train...")
			else:
				print("Load Checkpoint Failed")


		if self.multi_thread : 
			# in multi thread model, the image data were read in by dataset.get_train_indices()
			# and dataset.read_train_image_by_index()
			while True:
				epoch, batch_x, batch_y = self.train_data_queue.get()
				step = self.train_inner(epoch, batch_x, batch_y, sess, model, dataset)
				if step > int(self.config['train steps']):
					break
		else:
			epoch = 0
			while True:
				# in single thread model, the image data were read in by dataset.iter_train_images()
				for ind, batch_x, batch_y in dataset.iter_train_images_supervised():
					step = self.train_inner(epoch, batch_x, batch_y, sess, model, dataset)
					if step > int(self.config['train steps']):
						return
				epoch += 1

		# join all thread when in multi thread model
		self.coord.request_stop()
		while not self.train_data_queue.empty():
			epoch, batch_x, batch_y = self.train_data_queue.get()
		self.train_data_inner_queue.task_done()
		self.train_data_queue.task_done()
		self.coord.join(threads)

