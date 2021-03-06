


import os
import sys
sys.path.append('../')




def get_discriminator(name, config, is_training):
	if name == 'discriminator':
		from .discriminator_simple import DiscriminatorSimple
		return DiscriminatorSimple(config, is_training)
	elif name == 'cifar10 discriminator' or name == 'discriminator_cifar10':
		from .discriminator_cifar10 import DiscriminatorCifar10
		return DiscriminatorCifar10(config, is_training)

	elif name == 'discriminator_conv':
		from .discriminator_conv import D_conv
		return D_conv(config, is_training)
	else : 
		raise Exception("None discriminator named " + name)

