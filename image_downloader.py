from json.decoder import JSONDecodeError
from typing import OrderedDict
import requests
import json
from requests.auth import HTTPBasicAuth
from pathlib import Path
import click
import sys
from yaml import safe_load, YAMLError

from datetime import date, datetime

CODE_MAP = {
    "00080020":"Study Date",
    "00080030":"Study Time",
    "00100020":"Patient ID",
    "00081190":"Retrieve URL",
    "0020000D":"Study Instance UID",
    "00200010":"Study ID",
    "00201206":"Number of Study Related Series",

    "00080021":"Series Date",
    "00080031":"Series Time",
    "0008103E":"Series Description",
    "00081190":"Retrieve URL",
    "0020000E":"Series Instance UID",
    "00201209":"Number of Series Related Instances",

    "00080012":"Instance Creation Date",
    "00080013":"Instance Creation Time",
    "00200013":"Instance Number",
    "00280008":"Number of Frames",
    "00080018":"SOP Instance UID"
}

BASE_URL = "https://pacs.bric.unc.edu/pacsone"
QUERY_URL = f"{BASE_URL}/qidors.php"
RETRIEVAL_URL = f"{BASE_URL}/wadors.php"

def get_studies_by_date(auth, fetch_date: date=date.today()):
    """ Get any studies available on current date.

    Args:
        fetch_date (date, optional): [description]. Defaults to date.today().

    Returns:
        dict: study information
    """
    print(f"Fetching study by date: {fetch_date}")

    # Convert to date format expected by the API
    fetch_date_api_format = fetch_date.strftime("%Y%m%d")
    print(f"Date API format: {fetch_date_api_format}")

    # Add date to query params
    params = {'StudyDate':fetch_date_api_format}
    print("Performing study lookup")

    # Perform query
    response = requests.get(f"{QUERY_URL}/studies", auth=auth, params=params)

    # Load response json
    raw_studies = json.loads(response.text)
    print(f"Found {len(raw_studies)} studies")
    
    # Setup study dict
    studies = []
    for study in raw_studies:
        patient_id = study["00100020"]["Value"][0]
        study_id = study["0020000D"]["Value"][0]

        studies.append({"study_id":study_id, "patient_id":patient_id, "series":{}})

    return studies

def get_series_by_study_and_date(study_id, auth, fetch_date: date=date.today()):
    print(f"Fetching series by date: {fetch_date} and study id: {study_id}")

    fetch_date_api_format = fetch_date.strftime("%Y%m%d")
    print(f"Date API format: {fetch_date_api_format}")

    params = {'SeriesDate':fetch_date_api_format}
    print("Performing series lookup")
    response = requests.get(f"{QUERY_URL}/studies/{study_id}/series", auth=auth, params=params)

    try:
        raw_series = json.loads(response.text)
    except JSONDecodeError:
        raise JSONDecodeError("Series not found")
    print(f"Found {len(raw_series)} series")

    series = []

    for series_item in raw_series:
            series_id = series_item["0020000E"]["Value"][0]
            series_description = series_item["0008103E"]["Value"][0]
            
            series.append({"series_id":series_id, "series_description": series_description, "instances":{}})

    return series

def get_instances_by_study_series(study_id, series_id, auth):
    print(f"Fetching instance by study, series id: {series_id}")

    print("Performing instance lookup")
    response = requests.get(f"{QUERY_URL}/studies/{study_id}/series/{series_id}/instances", auth=auth)

    raw_instances = json.loads(response.text)
    print(f"Found {len(raw_instances)} instances")

    instances = []
    for instance in raw_instances:

        instance_id = instance["00080018"]["Value"][0]
        instance_number = instance["00200013"]["Value"][0]

        instances.append({"instance_id":instance_id, "instance_number": instance_number})

    return instances

def download_instance(study_id, series_id, instance_id, target_path, auth):

    url = f"{RETRIEVAL_URL}/{study_id}/series/{series_id}/instance/{instance_id}"

    response = requests.get(url, auth=auth)

    # trims off non-dicom portion of response body
    trimmed_response_content = response.content[112:]

    with open(target_path, mode='wb') as file:     
        file.write(trimmed_response_content)

def print_items(items: dict):
    for item in items:
        print("\n")
        for code in item:
            try:
                value = CODE_MAP[code]
            except KeyError:
                value = code
            print(f"{value}: {item[code]['Value']}")

@click.command()
@click.option('--fetch_date', '-d')
@click.option('--auth_file', '-a')  
def get_studies(fetch_date, auth_file):
    if fetch_date is None:
        fetch_date = date.today()
    else:
        fetch_date = datetime.strptime(fetch_date, "%Y-%m-%d")

    auth = get_auth(auth_file=auth_file)
    studies = get_studies_by_date(auth, fetch_date=fetch_date)

    if studies:
        print("Options:")
        for index, study in enumerate(studies):
            print(f"[{index}]: {studies[index]['patient_id']}")

        value = click.prompt(f'Choose a study to download ({0} - {len(studies) - 1})', type=int)
        if value < 0 or value > len(studies) - 1:
            print("Invalid option")
            sys.exit()
        chosen_study = studies[value]
        print(f"Processing study: {chosen_study['patient_id']}")
        

        series = get_series_by_study_and_date(chosen_study["study_id"], auth, fetch_date=input_date)

        for index, series_item in enumerate(series):
            print(f"[{index}]: {series[index]['series_description']}")
        print(f"[{len(series)}]: ALL SERIES")

        value = click.prompt(f'Choose a series to download ({0} - {len(series)})', type=int)
        if value < 0 or value > len(series):
            print("Invalid option")
            sys.exit()
        
        series_to_process = []
        # if a single series was chosen
        if value < len(series):
            series_to_process.append(series[value])
        else:
            series_to_process += series

        study_path = Path(chosen_study['patient_id'])
        study_path.mkdir(exist_ok=True)

        for series_item in series_to_process:
            series_path = Path(study_path / series_item['series_description'])
            series_path.mkdir(exist_ok=True)

            instances = get_instances_by_study_series(chosen_study["study_id"], series_item["series_id"], auth)

            print(f"Downloading series: {series_item['series_description']}")

            for index, instance in enumerate(instances):
                print(f"Downloading instance {index + 1} of {len(instances)}")
                instance_path = series_path / Path(instance['instance_id'] + ".dcm")
                download_instance(chosen_study["study_id"], series_item['series_id'], instance['instance_id'], instance_path, auth)
        
    else:
        print("No studies found for this date")

def get_auth(auth_file: str=None):
    if not auth_file: 
        print('No auth file providing - checking current directory for "pacs_credentials.yaml"')
        auth_file = 'pacs_credentials.yaml'
        
    with open(auth_file) as file:
        try:
            creds = safe_load(file)
            username = creds['username']
            password = creds['password']
        except YAMLError as ye:
            print(ye)

    return HTTPBasicAuth(username, password)


if __name__ == '__main__':
    get_studies()