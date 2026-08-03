"""
Usage: python -m scripts.retrain_prophet
"""

import logging
 
from app.core import setup_logging
from app.features.forecast.services.retrain import retrain_all_zones
 
setup_logging()
logger = logging.getLogger(__name__)
 
 
def run():
    results = retrain_all_zones()
    print("Prophet retrain results:")
    for zone, info in results.items():
        print(f"  - {zone}: {info}")
 
 
if __name__ == "__main__":
    run()