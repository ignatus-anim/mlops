from locust import HttpUser, task, between
import random

class InferenceUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Get available locations on start"""
        response = self.client.get("/api/get_location_names")
        if response.status_code == 200:
            self.locations = response.json().get('locations', ['1st Block Jayanagar'])
        else:
            self.locations = ['1st Block Jayanagar', 'Whitefield', 'Electronic City']
    
    @task(3)
    def predict_home_price(self):
        """Make prediction requests - most common task"""
        data = {
            'total_sqft': random.randint(500, 3000),
            'location': random.choice(self.locations),
            'bhk': random.randint(1, 4),
            'bath': random.randint(1, 3)
        }
        
        with self.client.post("/api/predict_home_price", data=data, catch_response=True) as response:
            if response.status_code == 200:
                json_data = response.json()
                if 'estimated_price' in json_data and json_data['estimated_price'] > 0:
                    response.success()
                else:
                    response.failure("Invalid prediction response")
            else:
                response.failure(f"Got status code {response.status_code}")
    
    @task(1)
    def health_check(self):
        """Health check requests"""
        with self.client.get("/api/health", catch_response=True) as response:
            if response.status_code == 200:
                json_data = response.json()
                if json_data.get('status') == 'healthy':
                    response.success()
                else:
                    response.failure("Service not healthy")
            else:
                response.failure(f"Health check failed with {response.status_code}")
    
    @task(1)
    def get_metrics(self):
        """Metrics endpoint requests"""
        self.client.get("/api/metrics")
    
    @task(1)
    def get_locations(self):
        """Location names requests"""
        self.client.get("/api/get_location_names")