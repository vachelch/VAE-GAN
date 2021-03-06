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
from time import *

sys.path.append('.')
sys.path.append('../')

import tensorflow as tf

from validator.validator import get_validator

class BaseTrainer(object):
	'''
		the base trainer for SupervisedTrainer, UnsupervisedTrainer. SemisupervisedTrainer
		implemention of several util functions for training.
		including the validator support, multi-thread data reading

		optional parameters including:
			path parameters:
			'summary dir'
			'checkpoint dir'

			step parameters:
			'log steps':
			'save steps':
			'summary steps':

			other parameters:
			'batch_size':
	'''
	def __init__(self, config, model, sess):

		assert(isinstance(config, dict))
		
		self.config = config
		self.model = model

		self.summary_dir = os.path.join(self.config['assets dir'], self.config.get('summary dir', 'log'))
		self.checkpoint_dir = os.path.join(self.config['assets dir'], self.config.get('checkpoint dir', 'checkpoint'))
		self.load_checkpoint_dir = os.path.join(self.config.get('load checkpoint assets dir', self.config['assets dir']),
												self.config.get('checkpoint dir', 'checkpoint'))

		self.summary_steps = int(self.config.get('summary steps', 0))
		self.log_steps = int(self.config.get('log steps', 0))
		self.save_checkpoint_steps = int(self.config.get('save checkpoint steps', 0))
		self.batch_size = int(self.config.get('batch_size', 16))


		if self.summary_steps != 0 and not os.path.exists(self.summary_dir):
			os.mkdir(self.summary_dir)
		if self.save_checkpoint_steps != 0 and not os.path.exists(self.checkpoint_dir):
			os.mkdir(self.checkpoint_dir)

		self.validator_list = []
		for validator_config in self.config.get('validators', []):
			validator_params = validator_config.get('validator params', {})
			validator_params['assets dir'] = self.config['assets dir']
			validator = get_validator(validator_config['validator'], validator_params)

			if validator.has_summary:
				validator.build_summary(self.model)

			validator_steps = int(validator_config['validate steps'])
			self.validator_list.append((validator_steps, validator))


		self.debug = self.config.get('debug', False)
		if self.debug:
			print('Trainer Parameters :')
			print('\tsummary_dir : ', self.summary_dir)
			print('\tcheckpoint_dir : ', self.checkpoint_dir)
			print('\tload_checkpoint_dir : ', self.load_checkpoint_dir)
			print('\tsummary_steps : ', self.summary_steps)
			print('\tlog_steps : ', self.log_steps)
			print('\tsave_checkpoint_steps : ', self.save_checkpoint_steps)
			print('\tbatch_size : ', self.batch_size)

		self.moving_time_pre_step = -1.0
		self.moving_time_decay = 0.03

		if 'summary hyperparams string' in self.config:
			self.summary_writer = tf.summary.FileWriter(self.summary_dir + '/' + self.config['summary hyperparams string'], sess.graph)
		else:
			self.summary_writer = tf.summary.FileWriter(self.summary_dir, sess.graph)
		
	#
	#	please implement the following functions in derived class
	#
	def train(self, sess, dataset, model):
		raise NotImplementedError


	def train_initialize(self, sess, model):
		"""
		"""
		self.sess = sess
		sess.run(tf.global_variables_initializer())
		sess.run(tf.local_variables_initializer())
		if self.config.get('continue train', False) and model.load_checkpoint(sess, self.load_checkpoint_dir):
			print("Load Checkpoint Success, Continue Train...")
		else:
			print("Load Pre-trained Weight... ")
			if model.load_pretrained_weights(sess):
				print("Success")
			else:
				print("Failed")



	def train_inner_step(self, epoch, model, validate_dataset, batch_x, batch_y=None, log_disp=True):
		"""
		the inner function for train a batch of images,
			input :
				epoch, batch_x, batch_y : train batch,
				model : 
				dataset : 
			return :
				step : the current train step
		"""

		start_time = clock()

		if batch_y is None:
			step, lr, loss, summary = model.train_on_batch_unsupervised(self.sess, batch_x)
			self.unsu_step = step
			self.unsu_lr = lr
			self.unsu_loss = loss
		else:
			step, lr, loss, summary = model.train_on_batch_supervised(self.sess, batch_x, batch_y)
			self.su_step = step
			self.su_lr = lr
			self.su_loss = loss

		time_elapsed = clock() - start_time
		self.moving_time_pre_step = (time_elapsed if self.moving_time_pre_step<0 
										else time_elapsed * self.moving_time_decay + (1.0 - self.moving_time_decay) * self.moving_time_pre_step)
	
		if self.summary_steps != 0 and summary is not None:
			if isinstance(summary, list):
				for s, summ in summary:
					self.summary_writer.add_summary(summ, s)
			else:
				self.summary_writer.add_summary(summary, step)

		if log_disp and self.log_steps != 0 and (step % self.log_steps == 0 or step <= 5):
			print("epoch : " + str(epoch)       
					+ ", step : " + str(step)
					+ ", lr : " + str(lr) 
					+ ", loss : " + str(loss)
					+ " (%0.3fs/step)"%(self.moving_time_pre_step))

		if self.summary_steps != 0 and (step % self.summary_steps == 0 or step == 1):
			summary = model.summary(self.sess)
			if summary:
				self.summary_writer.add_summary(summary, step)

		if self.save_checkpoint_steps != 0 and step % self.save_checkpoint_steps == 0:
			model.save_checkpoint(self.sess, self.checkpoint_dir, step)

		for validator_steps, validator in self.validator_list:
			if validator_steps != 0 and step % validator_steps == 0:
				summary = validator.validate(model, validate_dataset, self.sess, step)
				if summary is not None:
					if isinstance(summary, list):
						for s, summ in summary:
							self.summary_writer.add_summary(summ, s)
					else:
						self.summary_writer.add_summary(summary, step)

		return step


	#
	#	util functions for read dataset images in multiple thread
	#	
	def read_data_loop(self, coord, dataset, data_inner_queue, phase='train', method='supervised', nb_threads=4):
		"""create multiple threads to read data into @param.data_inner_queue
		"""
		def read_data_inner_loop(coord, dataset, 
			data_inner_queue, indices, t_ind, nb_threads,
			epoch, phase='train', method='supervised'):
			""" read data and put into @param.data_inner_queue in loop
			"""

			if method == 'supervised':
				for i, ind in enumerate(indices):
					if not coord.should_stop():
						if i % nb_threads == t_ind:
							# read img and label by its index
							img, label = dataset.read_image_by_index(ind, phase, method)
							if isinstance(img, list) and isinstance(label, list):
								for _img, _label in zip(img, label):
									data_inner_queue.put((epoch, img, label))
							elif img is not None:
								data_inner_queue.put((epoch, img, label))
					else:
						break
			elif method == 'unsupervised':
				for i, ind in enumerate(indices):
					if not coord.should_stop():
						if i % nb_threads == t_ind:
							# read img by its index
							img = dataset.read_image_by_index(ind, phase, method)
							if isinstance(img, list):
								for _img in img:
									if _img is not None:
										data_inner_queue.put((epoch, _img))
							elif img is not None:
								data_inner_queue.put((epoch, img))
					else:
						break
			else:
				raise Exception("wrong method of " + method)

		epoch = 0
		nb_threads = int(self.config.get('nb threads', nb_threads))
		while not coord.should_stop():

			# get train image indices of one epoch
			indices = dataset.get_image_indices(phase=phase, method=method)

			# create multiple thread to read data
			threads = [threading.Thread(target=read_data_inner_loop, 
								args=(coord, dataset, data_inner_queue, 
										indices, t_ind, nb_threads, 
										epoch, phase, method)) for t_ind in range(nb_threads)]
			for t in threads:
				t.start()
			coord.join(threads)
			epoch += 1


	def read_data_transport_loop(self, coord, data_inner_queue, data_queue, phase='train', method='supervised'):
		""" Take data from @param.data_inner_queue into batches and put to @param.data_queue
		"""
		epoch_list = []
		batch_x = []
		batch_y = []

		if method == 'supervised':
			while not coord.should_stop():
				epoch, img, label = data_inner_queue.get()
				epoch_list.append(epoch)
				batch_x.append(img)
				batch_y.append(label)

				if len(batch_x) == self.batch_size:
					epoch = np.array(epoch_list).min()
					batch_x = np.array(batch_x)
					batch_y = np.array(batch_y)
					data_queue.put((epoch, batch_x, batch_y))
					epoch_list = []
					batch_x = []
					batch_y = []
					
			# clear the data inner queue to free the (read_data_inner_loop) thread
			while not data_inner_queue.empty():
				epoch, img, label = data_inner_queue.get()

		elif method == 'unsupervised':
			while not coord.should_stop():			
				epoch, img = data_inner_queue.get()
				epoch_list.append(epoch)
				batch_x.append(img)

				if len(batch_x) == self.batch_size:
					epoch = np.array(epoch_list).min()
					batch_x = np.array(batch_x)
					data_queue.put((epoch, batch_x))
					epoch_list = []
					batch_x = []

			# clear the data inner queue to free the (read_data_inner_loop) thread
			while not data_inner_queue.empty():
				epoch, img = data_inner_queue.get()

		else:
			raise Exception("wrong method of " + method)

