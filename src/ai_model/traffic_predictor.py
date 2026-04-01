"""
AI Traffic Prediction Model
LSTM-based time series forecasting for 5G traffic
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import json
import logging

# TensorFlow/Keras imports (will be installed via requirements.txt)
try:
    from tensorflow import keras
    from tensorflow.keras import layers, models
    from tensorflow.keras.preprocessing.sequence import TimeseriesGenerator
    import tensorflow as tf
except ImportError:
    print("TensorFlow not installed. Install via: pip install tensorflow")

logger = logging.getLogger(__name__)


class TrafficPredictor:
    """
    LSTM-based traffic prediction model
    Predicts future traffic loads based on historical patterns
    """
    
    def __init__(self, lookback_window: int = 24, prediction_horizon: int = 24):
        """
        Initialize predictor
        
        Args:
            lookback_window: Hours of historical data to use (default 24h)
            prediction_horizon: Hours ahead to predict (default 24h)
        """
        self.lookback_window = lookback_window
        self.prediction_horizon = prediction_horizon
        self.model = None
        self.scaler_mean = None
        self.scaler_std = None
        self.is_trained = False
        
    def prepare_data(self, traffic_data: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare data for LSTM training
        
        Args:
            traffic_data: DataFrame with columns like 'active_users', 'data_mbps', 'energy_w'
        
        Returns:
            X, y training arrays
        """
        # Use active_users as primary metric
        if 'active_users' not in traffic_data.columns:
            raise ValueError("traffic_data must contain 'active_users' column")
        
        data = traffic_data['active_users'].values.reshape(-1, 1).astype(np.float32)
        
        # Normalize data
        self.scaler_mean = np.mean(data)
        self.scaler_std = np.std(data)
        data = (data - self.scaler_mean) / (self.scaler_std + 1e-8)
        
        X, y = [], []
        
        for i in range(len(data) - self.lookback_window - self.prediction_horizon):
            X.append(data[i:i + self.lookback_window])
            y.append(data[i + self.lookback_window:i + self.lookback_window + self.prediction_horizon])
        
        return np.array(X), np.array(y)
    
    def build_model(self):
        """Build LSTM model architecture"""
        model = keras.Sequential([
            layers.LSTM(64, activation='relu', input_shape=(self.lookback_window, 1), 
                       return_sequences=True),
            layers.Dropout(0.2),
            layers.LSTM(32, activation='relu', return_sequences=False),
            layers.Dropout(0.2),
            layers.Dense(16, activation='relu'),
            layers.Dense(self.prediction_horizon)
        ])
        
        model.compile(
            optimizer='adam',
            loss='mse',
            metrics=['mae']
        )
        
        self.model = model
        return model
    
    def train(self, traffic_data: pd.DataFrame, epochs: int = 50, batch_size: int = 32,
              validation_split: float = 0.2):
        """
        Train the LSTM model
        
        Args:
            traffic_data: DataFrame with historical traffic
            epochs: Number of training epochs
            batch_size: Batch size for training
            validation_split: Fraction of data for validation
        """
        X, y = self.prepare_data(traffic_data)
        
        if len(X) == 0:
            raise ValueError("Not enough data to train. Need at least lookback + prediction_horizon samples")
        
        self.build_model()
        
        history = self.model.fit(
            X, y,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=validation_split,
            verbose=1,
            callbacks=[
                keras.callbacks.EarlyStopping(
                    monitor='val_loss',
                    patience=5,
                    restore_best_weights=True
                )
            ]
        )
        
        self.is_trained = True
        return history
    
    def predict(self, recent_data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict future traffic
        
        Args:
            recent_data: Last 24 hours of traffic data (array of shape (24,))
        
        Returns:
            Predicted values and confidence intervals
        """
        if not self.is_trained:
            raise RuntimeError("Model must be trained before prediction")
        
        # Normalize input
        recent_data_norm = (recent_data - self.scaler_mean) / (self.scaler_std + 1e-8)
        recent_data_norm = recent_data_norm.reshape(1, -1, 1)
        
        # Predict
        prediction_norm = self.model.predict(recent_data_norm, verbose=0)
        
        # Denormalize
        prediction = prediction_norm * (self.scaler_std + 1e-8) + self.scaler_mean
        prediction = np.maximum(prediction, 0)  # No negative traffic
        
        # Calculate confidence intervals (±15%)
        confidence = prediction * 0.15
        
        return prediction[0], confidence[0]
    
    def predict_next_hours(self, recent_data: np.ndarray, num_hours: int = 24) -> Dict:
        """
        Predict next N hours with detailed breakdown
        
        Args:
            recent_data: Last 24 hours of active users
            num_hours: Number of hours to predict (default 24)
        
        Returns:
            Dictionary with predictions and metadata
        """
        predictions, confidence = self.predict(recent_data)
        
        # Truncate to requested hours
        predictions = predictions[:num_hours]
        confidence = confidence[:num_hours]
        
        hours_ahead = np.arange(1, len(predictions) + 1)
        
        result = {
            'predictions': predictions.tolist(),
            'confidence_intervals': confidence.tolist(),
            'hours_ahead': hours_ahead.tolist(),
            'peak_load': float(np.max(predictions)),
            'peak_hour': int(np.argmax(predictions) + 1),
            'average_load': float(np.mean(predictions)),
            'min_load': float(np.min(predictions)),
            'min_hour': int(np.argmin(predictions) + 1)
        }
        
        return result
    
    def save_model(self, filepath: str):
        """Save trained model to disk"""
        if not self.is_trained:
            raise RuntimeError("No trained model to save")
        
        self.model.save(filepath)
        
        # Also save scalers
        scalers = {
            'mean': float(self.scaler_mean),
            'std': float(self.scaler_std),
            'lookback_window': self.lookback_window,
            'prediction_horizon': self.prediction_horizon
        }
        
        scaler_file = filepath.replace('.h5', '_scaler.json')
        with open(scaler_file, 'w') as f:
            json.dump(scalers, f)
        
        logger.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath: str):
        """Load trained model from disk"""
        self.model = keras.models.load_model(filepath)
        
        scaler_file = filepath.replace('.h5', '_scaler.json')
        with open(scaler_file, 'r') as f:
            scalers = json.load(f)
        
        self.scaler_mean = scalers['mean']
        self.scaler_std = scalers['std']
        self.lookback_window = scalers['lookback_window']
        self.prediction_horizon = scalers['prediction_horizon']
        self.is_trained = True
        
        logger.info(f"Model loaded from {filepath}")


# Simpler statistical predictor (no TensorFlow required)
class SimplePredictor:
    """
    Simple statistical predictor using historical patterns
    Useful as baseline or when TensorFlow is not available
    """
    
    def __init__(self, lookback_window: int = 24):
        self.lookback_window = lookback_window
        self.hourly_patterns = {}  # Hour -> [avg, std]
        
    def train(self, traffic_data: pd.DataFrame):
        """
        Train on historical data
        Extract hourly patterns
        """
        # Extract hour from timestamp and group
        if 'timestamp' in traffic_data.columns:
            traffic_data['hour'] = pd.to_datetime(traffic_data['timestamp']).dt.hour
        else:
            traffic_data['hour'] = range(len(traffic_data)) % 24
        
        for hour in range(24):
            hour_data = traffic_data[traffic_data['hour'] == hour]['active_users']
            if len(hour_data) > 0:
                self.hourly_patterns[hour] = {
                    'mean': hour_data.mean(),
                    'std': hour_data.std() or 10
                }
    
    def predict_next_hours(self, num_hours: int = 24) -> Dict:
        """Predict next 24 hours based on hourly patterns"""
        if not self.hourly_patterns:
            raise RuntimeError("Model not trained. Call train() first.")
        
        current_hour = datetime.now().hour
        predictions = []
        
        for i in range(num_hours):
            hour = (current_hour + i) % 24
            pattern = self.hourly_patterns.get(hour, {'mean': 100, 'std': 20})
            predictions.append(pattern['mean'])
        
        return {
            'predictions': predictions,
            'confidence_intervals': [p * 0.15 for p in predictions],
            'hours_ahead': list(range(1, num_hours + 1)),
            'peak_load': max(predictions),
            'peak_hour': predictions.index(max(predictions)) + 1,
            'average_load': np.mean(predictions),
            'min_load': min(predictions),
            'min_hour': predictions.index(min(predictions)) + 1
        }


if __name__ == "__main__":
    # Example usage
    print("Traffic Prediction Module loaded")
