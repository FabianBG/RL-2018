import gym
import numpy as np
import tensorflow as tf
import random
from skimage.transform import downscale_local_mean
import time
from tensorflow.python.saved_model import tag_constants
import os, argparse


class Playground:

	def __init__(self, game, num_hidden_layers, layer_sizes, epsilon_max, epsilon_min, alpha, gamma, batch_size, memory_capacity,
		steering, acceleration, deceleration):
		self.game = game
		self.num_hidden_layers = num_hidden_layers
		self.layer_sizes = layer_sizes
		self.epsilon_max = epsilon_max
		self.epsilon_min = epsilon_min
		self.alpha = alpha
		self.gamma = gamma
		self.batch_size = batch_size
		self.memory_capacity = memory_capacity
		self.history_pick = 4
		self.steering = steering
		self.acceleration = acceleration
		self.deceleration = deceleration
		self.steering_size = len(self.steering)
		self.acceleration_size = len(self.acceleration)
		self.deceleration_size = len(self.deceleration)
		self.dir = os.path.dirname(os.path.realpath('deep_q_car_gpu.py'))
		# self.Q_eval_states = np.load('random_sample.npy')
		# self.Q_eval_states_len = np.shape(self.Q_eval_states)[0]
		self.initialize_tf_variables()

	def rgb2gray(self, rgb):
		return np.dot(rgb, [0.299, 0.587, 0.114])
	
	def down_sample(self, state):
		state = self.rgb2gray(state)#self.rgb2gray(state[:82,:])
		return downscale_local_mean(state, (2, 2))

	def get_state_space_size(self, state):
		return np.shape(self.down_sample(state))

	# def Q_nn(self, x):
	# 	with tf.device('/device:GPU:0'):
	# 		layer1_out = tf.layers.conv2d(x, filters=16, kernel_size=[8,8], strides=[4,4], padding='same', activation=tf.nn.relu, data_format='channels_last') # => 23x23x16
	# 		layer2_out = tf.layers.conv2d(layer1_out, filters=32, kernel_size=[4,4], strides=[2,2], padding='same', activation=tf.nn.relu, data_format='channels_last') # => 9x9x32
	# 		layer2_shape = np.prod(np.shape(layer2_out)[1:])
	# 		layer3_out = tf.layers.dense(tf.reshape(layer2_out, [-1,layer2_shape]), 256, activation=tf.nn.relu) # => 1x256
	# 		output = tf.layers.dense(layer3_out, self.action_size, activation=None)
	# 		return output # => 1x45

	def Q_nn(self, x):
		with tf.device('/device:GPU:0'):
			layer1_out = tf.layers.conv2d(x, filters=16, kernel_size=[8,8], strides=[4,4], padding='same', activation=tf.nn.relu, data_format='channels_first') # => 23x23x16
			layer1_shape = np.prod(np.shape(layer1_out)[1:])
			layer2_out = tf.nn.dropout(tf.layers.dense(tf.reshape(layer1_out, [-1,layer1_shape]), 64, activation=tf.nn.relu), .5) # => 1x256
			output = tf.layers.dense(layer2_out, self.action_size, activation=None)
			return output # => 1x45

	# def avg_Q_val(self):
	# 	q_avg_est = 0
	# 	print 'Hi, JJ!'
	# 	for state in self.Q_eval_states:
	# 		q_avg_est += self.sess.run(self.Q_amax, feed_dict={self.state_tf: [[state, state, state, state]]})
	# 	return q_avg_est/self.Q_eval_states_len

	# action index is 0 - 3
	def map_action(self, action_index):
		return [[-1, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 0.8]][action_index]

	# def map_action(self, action_index):
	# 	s = self.steering[action_index/(self.acceleration_size*self.deceleration_size)]
	# 	a = self.acceleration[(action_index/self.deceleration_size)%self.acceleration_size]
	# 	d = self.deceleration[action_index%self.deceleration_size]
	# 	return [s,a,d]

	def initialize_tf_variables(self):
		# Setting up game specific variables
		self.env = gym.make(self.game)
		self.state_size = self.get_state_space_size(self.env.reset())
		self.lower_bounds = self.env.observation_space.low
		self.upper_bounds = self.env.observation_space.high
		self.action_size = 4
		#self.action_size = self.steering_size*self.acceleration_size*self.deceleration_size
		# Tf placeholders
		self.state_tf = tf.placeholder(shape=[None, self.history_pick, 48, 48], dtype=tf.float64)
		self.action_tf = tf.placeholder(shape=[None, self.action_size], dtype=tf.float64)
		self.y_tf = tf.placeholder(dtype=tf.float64)

		# Operations
		self.Q_value = self.Q_nn(self.state_tf)
		self.Q_argmax = tf.argmax(self.Q_value[0])
		self.Q_amax = tf.reduce_max(self.Q_value[0])
		self.Q_value_at_action = tf.reduce_sum(tf.multiply(self.Q_value, self.action_tf), axis=1)
		
		# Training related
		self.loss = tf.reduce_mean(tf.square(self.y_tf - self.Q_value_at_action))
		self.train_op = tf.train.AdamOptimizer(learning_rate=self.alpha).minimize(self.loss)
		self.fixed_weights = None

		# Tensorflow session setup
		config = tf.ConfigProto()
		config.allow_soft_placement=False
		config.gpu_options.allow_growth = True
		config.log_device_placement = True
		self.sess = tf.Session(config = config)
		self.trainable_variables = tf.trainable_variables()
		self.sess.run(tf.global_variables_initializer())
		self.sess.graph.finalize()

	def phi(self, states):
		hist_size = np.shape(states)[0]
		return_size = np.amin([self.history_pick, hist_size])
		ret_vec = [states[i] for i in range(hist_size)[(hist_size - return_size):]]
		return ret_vec

	def get_batch(self, replay_memory):
		mini_batch = random.sample(replay_memory, self.batch_size)
		state_batch = [data[0] for data in mini_batch]
		action_batch = [data[1] for data in mini_batch]
		reward_batch = [data[2] for data in mini_batch]
		next_state_batch = [data[3] for data in mini_batch]
		done_batch = [data[4] for data in mini_batch]
		return state_batch, action_batch, reward_batch, next_state_batch, done_batch

	def experience_replay(self, replay_memory, frame):
		state_batch, action_batch, reward_batch, next_state_batch, done_batch = self.get_batch(replay_memory)
		y_batch = [None] * self.batch_size
		dict = {self.state_tf: next_state_batch}
		dict.update(zip(self.trainable_variables, self.fixed_weights))
		Q_value_batch = self.sess.run(self.Q_value, feed_dict=dict)
		for i in range(self.batch_size):
			y_batch[i] = reward_batch[i] + (0 if done_batch[i] else self.gamma * np.max(Q_value_batch[i]))

		if (frame % 100 == 0):
			self.sess.run(self.train_op, feed_dict={self.y_tf: y_batch, self.action_tf: action_batch, 
			self.state_tf: state_batch})
   
	def get_random_action(self):
		return np.random.randint(0, 4)

	def get_action(self, state, epsilon):
		if random.random() < epsilon:
			return self.get_random_action()
		else:
			return self.sess.run(self.Q_argmax, feed_dict={self.state_tf: [state]})

	def update_fixed_weights(self):
		self.fixed_weights = self.sess.run(self.trainable_variables)

	def begin_training(self, num_episodes, k):
		eps_decay_rate = (self.epsilon_min - self.epsilon_max) / num_episodes
		# q_averages = np.zeros(num_episodes)
		replay_memory = []
		print 'Training...'
		rewards_vec = np.zeros(num_episodes)

		for episode in range(num_episodes):
			start_time = time.time()
			done = False
			tot_reward = 0
			frame = 0
			state = self.env.reset()
			state = self.down_sample(state)
			states = [state, state, state, state]
			self.env.render()
			self.update_fixed_weights()
			while not done and frame < 500:
				# Take action and update replay memory
				# self.env.render()
				phi = self.phi(states)
				if (frame % k) == 0:
					action = self.get_action(phi, self.epsilon_max + eps_decay_rate * episode)
				next_state, reward, done, _ = self.env.step(self.map_action(action))

				next_state = self.down_sample(next_state)

				states.append(next_state)
				phi_1 = self.phi(states)
				one_hot_action = np.zeros(self.action_size)
				one_hot_action[action] = 1
				replay_memory.append((phi, one_hot_action, reward, phi_1, done))

				# Check whether replay memory capacity reached
				if (len(replay_memory) > self.memory_capacity): 
					replay_memory.pop(0)

				# Perform experience replay if replay memory populated
				if len(replay_memory) > 10 * self.batch_size:
					self.experience_replay(replay_memory, frame)

				tot_reward += reward
				state = next_state
				# frame = (frame + 1) % k
				frame += 1
			# q_averages[episode] = self.estimate_avg_q(1000)
			rewards_vec[episode] = tot_reward
			print 'Episode: {}. Reward: {}'.format(episode, tot_reward)
			print 'Time: {} seconds'.format(time.time() - start_time)
			np.savetxt('CarRacingRewards.csv', rewards_vec, delimiter=',')

		# file_name = 'avg_q_' + self.game + '.csv'
		# np.savetxt(file_name, q_averages, delimiter=',')
		print '--------------- Done training ---------------'

		# saver = tf.train.Saver()
    	# last_chkp = saver.save(self.sess, dir + '/data-all.chkp')
	
	def test_Q(self, num_test_episodes):
		print 'Testing...'
		for episode in range(num_test_episodes):
			done = False
			tot_reward = 0
			state = self.env.reset()
			while not done:
				# Take action and update replay memory
				action = self.get_action(state, 0)
				next_state, reward, done, _ = self.env.step(action)
				tot_reward += reward
				state = next_state
				tot_reward += reward
			print 'Test {}: Reward = {}'.format(episode, tot_reward)