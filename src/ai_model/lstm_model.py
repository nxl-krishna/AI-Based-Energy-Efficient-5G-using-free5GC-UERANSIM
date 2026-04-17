"""
lstm_model.py
-------------
AI Agent for Energy Optimization
Implemented as an LSTM-based Deep Q-Network (DQN).
This agent takes system metrics as state and outputs the optimal number of active base stations.
"""

import numpy as np
import random
import os
import logging
from collections import deque
import pandas as pd

try:
    from tensorflow.keras import Sequential, layers
    from tensorflow.keras.optimizers import Adam
    HAS_KERAS = True
except ImportError:
    HAS_KERAS = False
    logging.warning("Tensorflow/Keras not installed. Install via: pip install tensorflow")

logger = logging.getLogger(__name__)

class EnergyOptimizationAgent:
    def __init__(self, state_size: int = 4, action_size: int = 10, max_bs: int = 10):
        """
        AI Agent that decides how many Base Stations should be active.
        
        Args:
            state_size: Number of features in the input state (e.g. UE, Throughput, CPU, Memory)
            action_size: Number of possible actions (e.g. 1 to 10 active base stations)
            max_bs: Maximum number of base stations in the network
        """
        self.state_size = state_size
        self.action_size = action_size
        self.max_bs = max_bs
        
        # Hyperparameters
        self.gamma = 0.95           # Discount factor
        self.epsilon = 1.0          # Exploration rate
        self.epsilon_min = 0.05
        self.epsilon_decay = 0.995
        self.learning_rate = 0.001
        self.batch_size = 32
        
        # Replay memory
        self.memory = deque(maxlen=2000)
        
        # Sequence tracking for LSTM (we need a time sequence of states)
        self.sequence_length = 5
        self.state_buffer = deque(maxlen=self.sequence_length)
        
        self.model = self._build_model() if HAS_KERAS else None
        self.is_trained = False

    def _build_model(self):
        """Build the LSTM-based DQN network."""
        model = Sequential([
            layers.LSTM(64, input_shape=(self.sequence_length, self.state_size), activation='relu'),
            layers.Dropout(0.2),
            layers.Dense(32, activation='relu'),
            layers.Dense(self.action_size, activation='linear')
        ])
        model.compile(loss='mse', optimizer=Adam(learning_rate=self.learning_rate))
        return model

    def get_sequence_state(self, current_state: np.ndarray) -> np.ndarray:
        """Maintains a rolling buffer to provide sequence inputs to the LSTM."""
        self.state_buffer.append(current_state)
        # Pad if buffer isn't full yet
        while len(self.state_buffer) < self.sequence_length:
            self.state_buffer.append(current_state)
            
        return np.array(self.state_buffer).reshape(1, self.sequence_length, self.state_size)

    def act(self, state: np.ndarray, is_training: bool = False) -> int:
        """
        Predict the optimal action (number of BS to activate).
        Returns an integer representing the active BS count (1 to action_size).
        """
        if not HAS_KERAS:
            return self.max_bs  # Fallback to all ON
            
        seq_state = self.get_sequence_state(state)
        
        if is_training and np.random.rand() <= self.epsilon:
            # Explore: random number of base stations
            return random.randint(1, self.action_size)
            
        # Exploit: predict Q-values
        act_values = self.model.predict(seq_state, verbose=0)
        # Returns action index (0 to action_size-1). We add 1 for BS count (1 to action_size)
        return int(np.argmax(act_values[0])) + 1

    def remember(self, state, action, reward, next_state, done):
        """Store experience in replay memory."""
        self.memory.append((state, action, reward, next_state, done))

    def replay(self):
        """Train the neural network using replay memory."""
        if len(self.memory) < self.batch_size or not HAS_KERAS:
            return
            
        minibatch = random.sample(self.memory, self.batch_size)
        
        # Prepare batch inputs
        states = []
        targets = []
        
        for state, action, reward, next_state, done in minibatch:
            target = reward
            if not done:
                seq_next = np.array([next_state] * self.sequence_length).reshape(1, self.sequence_length, self.state_size)
                target = (reward + self.gamma * np.amax(self.model.predict(seq_next, verbose=0)[0]))
                
            seq_curr = np.array([state] * self.sequence_length).reshape(1, self.sequence_length, self.state_size)
            target_f = self.model.predict(seq_curr, verbose=0)
            
            # Action is 1-indexed, so we subtract 1 for the array index
            target_f[0][action - 1] = target
            
            states.append(seq_curr[0])
            targets.append(target_f[0])
            
        self.model.fit(np.array(states), np.array(targets), epochs=1, verbose=0)
        
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
            
        self.is_trained = True

    def calculate_reward(self, energy_watts: float, throughput: float, ue_count: int, active_bs: int) -> float:
        """
        Calculates the reward for the agent.
        Goal: Minimize energy (Penalty) while sustaining high throughput per UE (Reward).
        """
        # Baseline energy penalty
        energy_penalty = - (energy_watts / 100.0)
        
        # Throughput reward (ensure we are servicing traffic properly)
        # Avoid division by zero
        safe_ue = max(1, ue_count)
        throughput_per_ue = throughput / safe_ue
        
        # If throughput completely drops, heavy penalty
        throughput_reward = throughput_per_ue * 10
        if throughput < 1.0 and ue_count > 10:
             throughput_reward -= 50
             
        # Efficiency bonus: higher reward if same throughput achieved with fewer BS
        efficiency_bonus = (self.max_bs - active_bs) * 2
        
        reward = energy_penalty + throughput_reward + efficiency_bonus
        return reward

    def train_offline(self, dataset_path: str):
        """Train the agent on historical data collected previously."""
        if not HAS_KERAS or not os.path.exists(dataset_path):
            logger.warning(f"Cannot train. Keras missing or path {dataset_path} not found.")
            return
            
        df = pd.read_csv(dataset_path)
        required_cols = ['UE', 'Throughput', 'CPU', 'Memory', 'Energy', 'active_bs']
        if not all(col in df.columns for col in required_cols):
            logger.error("Dataset missing required columns for training.")
            return

        logger.info(f"Starting offline training on {len(df)} samples...")
        
        # Simulate episodes over the dataset
        for index in range(len(df) - 1):
            row = df.iloc[index]
            next_row = df.iloc[index + 1]
            
            state = np.array([row['UE'], row['Throughput'], row['CPU'], row['Memory']])
            next_state = np.array([next_row['UE'], next_row['Throughput'], next_row['CPU'], next_row['Memory']])
            
            # The "action" taken in the historically collected row
            action = int(row['active_bs'])
            
            # Recompute reward based on what actually happened
            energy = row['Energy'] 
            reward = self.calculate_reward(energy, row['Throughput'], row['UE'], action)
            
            done = False
            self.remember(state, action, reward, next_state, done)
            
        # Replay extensively to learn Q-values
        for _ in range(50):
            self.replay()
            
        self.is_trained = True
        logger.info("Offline training completed.")

    def save(self, filepath: str):
        if self.model:
            self.model.save(filepath)
            
    def load(self, filepath: str):
        if HAS_KERAS and os.path.exists(filepath):
            from tensorflow.keras.models import load_model
            self.model = load_model(filepath)
            self.is_trained = True
            self.epsilon = self.epsilon_min
