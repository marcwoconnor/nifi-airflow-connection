from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.utils.dates import days_ago

from src.nifi.get_token import get_token
from src.nifi.update_processor_status import update_processor_status
from src.nifi.get_processor_state import get_processor_state

from src.utils.parse_state import parse_state
from src.utils.pause import pause


def prepare():
    """Where something happens before the NiFi pipeline is triggered."""
    pass


def startup():
    # Initialize the following variables according to your setup / needs:
    url_nifi_api = "https://your.cluster.address.com:9443/nifi-api/"
    processor_id = (
        ""  # e.g. hardcoded / pass them via the `provide_context` functionality
    )
    access_payload = {
        "username": "",
        "password": "",
    }  # e.g. retrieve via Airflow's `BaseHook` functionality

    token = get_token(url_nifi_api, access_payload)
    response = update_processor_status(processor_id, "RUNNING", token, url_nifi_api)
    print(response)
    pause(15)  # wait for 15 seconds to give NiFi time to create a flow file
    response = update_processor_status(processor_id, "STOPPED", token, url_nifi_api)
    print(response)


def wait_for_update():
    # Initialize the following variables according to your setup / needs:
    url_nifi_api = "https://your.cluster.address.com:9443/nifi-api/"
    processor_id = ""  # e.g. pass them via the DAG's `provide_context` functionality
    access_payload = ""  # e.g. retrieve the via Airflow's `BaseHook` functionality
    timestamp_property = "last_tms"  # the processor's attribute name

    token = get_token(url_nifi_api, access_payload)

    # Get current timestamp
    processor_state = get_processor_state(url_nifi_api, processor_id, token=token)
    value_start = parse_state(processor_state, timestamp_property)

    # query and wait until an update happens or we time out.
    while True:
        processor_state = get_processor_state(url_nifi_api, processor_id, token=token)
        value_current = parse_state(processor_state, timestamp_property)

        if value_start == value_current:
            print("Waiting...")
            pause(60)
        else:
            print(f"Update found: {value_current}")
            break


def finalize():
    pass


with DAG(
    dag_id="my_dag_name",
    schedule_interval=None,
    start_date=days_ago(2),
    catchup=False,
) as dag:

    preparation = PythonOperator(
        task_id="preparation",
        python_callable=prepare,
    )
    startup_task = PythonOperator(
        task_id="startup_task",
        python_callable=startup,
    )

    waiting_task = PythonOperator(
        task_id="waiting_task",
        python_callable=wait_for_update,
    )

    finalization = PythonOperator(
        task_id="finalization",
        python_callable=finalize,
    )
    # I had to change the order of tasks, The orginal was preparation >> startup_task >> waiting_task >> finalization
    # Which caused the waiting task to time out waiting for and updated tms entry, but the startup task had already sent the new flow file
    # So the update attribute processor was never aware of the initial tms value.
    preparation >> [startup_task , waiting_task]   >> finalization
