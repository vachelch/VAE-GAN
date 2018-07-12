import os
import sys

sys.path.append('.')
sys.path.append('../')

import tensorflow as tf
import matplotlib.pyplot as plt

from dataset.production import ChipProduction






if __name__ == '__main__':
	config = {
		'batch_size' : 16,
		'output shape' : [64, 64, 2]
	}

	dataset = ChipProduction(config)

	indices = dataset.get_image_indices('train')


	for ind in indices:
		image_list = dataset.read_image_by_index_unsupervised(ind)
		# for image in image_list:
		plt.figure(0)

		for ind, image in enumerate(image_list):
			if ind < 16:
				plt.subplot(4, 4, ind+1)
				plt.imshow(image[:, :, 0])
		plt.pause(3)



	# for ind, x_batch, y_batch in dataset.iter_train_images_supervised():
		# plt.figure(0)
		# plt.imshow(x_batch[0, :, :, :])
		# plt.pause(1)

	