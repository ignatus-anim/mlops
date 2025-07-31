"""
Airflow DAG for automated drift monitoring and alerting
"""
from datetime import datetime, timedelta
from airflow.decorators import dag, task
from airflow.operators.python import get_current_context
import sys
import os

# Add inference backend to path for imports
sys.path.append('/opt/airflow/inference/backend')

default_args = {
    'owner': 'mlops-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 7, 31),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

@dag(
    dag_id='drift_monitoring_dag',
    default_args=default_args,
    description='Monitor data drift and trigger alerts',
    schedule_interval='@daily',  # Run daily
    catchup=False,
    tags=['monitoring', 'drift', 'ml']
)
def drift_monitoring_dag():
    
    @task
    def check_data_drift():
        """Check for data drift and return results"""
        try:
            from drift_monitor import get_drift_summary, get_reference_data, get_current_data, check_drift_threshold, generate_drift_report
            
            # Get drift summary
            drift_summary = get_drift_summary()
            
            if drift_summary.get('status') != 'success':
                print(f"Drift check failed: {drift_summary}")
                return drift_summary
            
            # Check if significant drift detected
            drift_detected = drift_summary.get('overall_drift_detected', False)
            
            print(f"Drift monitoring results:")
            print(f"- Overall drift detected: {drift_detected}")
            print(f"- Data points: {drift_summary.get('data_points', {})}")
            
            # Log drift indicators
            for feature, indicator in drift_summary.get('drift_indicators', {}).items():
                if indicator.get('significant_drift'):
                    print(f"- {feature}: {indicator['drift_percentage']:.1f}% drift detected")
            
            return drift_summary
            
        except Exception as e:
            print(f"Error in drift monitoring: {e}")
            return {"status": "error", "message": str(e)}
    
    @task
    def evaluate_drift_impact(drift_results):
        """Evaluate drift impact and determine if action needed"""
        try:
            if drift_results.get('status') != 'success':
                return {"action": "none", "reason": "drift_check_failed"}
            
            drift_detected = drift_results.get('overall_drift_detected', False)
            
            if not drift_detected:
                return {"action": "none", "reason": "no_significant_drift"}
            
            # Count features with significant drift
            drift_indicators = drift_results.get('drift_indicators', {})
            significant_drifts = [
                feature for feature, indicator in drift_indicators.items()
                if indicator.get('significant_drift', False)
            ]
            
            # Determine action based on drift severity
            if len(significant_drifts) >= 2:  # Multiple features drifting
                return {
                    "action": "trigger_retraining",
                    "reason": f"significant_drift_in_{len(significant_drifts)}_features",
                    "drifted_features": significant_drifts
                }
            elif len(significant_drifts) == 1:
                return {
                    "action": "alert_only", 
                    "reason": f"drift_in_{significant_drifts[0]}",
                    "drifted_features": significant_drifts
                }
            
            return {"action": "none", "reason": "drift_below_threshold"}
            
        except Exception as e:
            print(f"Error evaluating drift impact: {e}")
            return {"action": "error", "reason": str(e)}
    
    @task
    def take_drift_action(action_plan):
        """Take appropriate action based on drift evaluation"""
        try:
            action = action_plan.get('action', 'none')
            reason = action_plan.get('reason', 'unknown')
            
            print(f"Drift action plan: {action} - {reason}")
            
            if action == 'trigger_retraining':
                print("🚨 SIGNIFICANT DRIFT DETECTED - Would trigger retraining")
                print(f"Drifted features: {action_plan.get('drifted_features', [])}")
                
                # In production, this would trigger the training DAG
                # from airflow.api.common.experimental.trigger_dag import trigger_dag
                # trigger_dag('bangalore_home_prices_dag', run_id=f'drift_triggered_{datetime.now().isoformat()}')
                
                return {"status": "retraining_triggered", "features": action_plan.get('drifted_features', [])}
                
            elif action == 'alert_only':
                print("⚠️  MODERATE DRIFT DETECTED - Monitoring required")
                print(f"Drifted features: {action_plan.get('drifted_features', [])}")
                
                return {"status": "alert_sent", "features": action_plan.get('drifted_features', [])}
                
            else:
                print("✅ NO SIGNIFICANT DRIFT - System stable")
                return {"status": "no_action_needed"}
                
        except Exception as e:
            print(f"Error taking drift action: {e}")
            return {"status": "error", "message": str(e)}
    
    # Define task dependencies
    drift_results = check_data_drift()
    action_plan = evaluate_drift_impact(drift_results)
    final_result = take_drift_action(action_plan)
    
    return final_result

# Instantiate the DAG
drift_dag = drift_monitoring_dag()