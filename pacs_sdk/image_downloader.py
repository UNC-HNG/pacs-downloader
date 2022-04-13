from json.decoder import JSONDecodeError
from urllib.error import HTTPError
import requests
import json
from requests.auth import HTTPBasicAuth
from pathlib import Path
import click
import sys
import re
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

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            raise ValueError("Invalid credentials provided - please check your username and password.")
        raise e


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
            series_number = series_item["00200011"]["Value"][0]
            
            series.append({"series_id":series_id, "series_description": series_description, "series_number":series_number, "instances":{}})

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

def download_instances(study_id, series_id, instances, series_path, auth):

    # Any once instance URL request gives back all instances for some reason - so
    # we can just take the first one
    instance_id = instances[0]['instance_id']

    url = f"{RETRIEVAL_URL}/{study_id}/series/{series_id}/instance/{instance_id}"
    headers = {"Accept": "application/dicom"}
    print(f"Downloading instances...")
    response = requests.get(url, headers=headers, auth=auth)

    from requests_toolbelt.multipart import decoder

    multipart_data = decoder.MultipartDecoder.from_response(response)

    for index, part in enumerate(multipart_data.parts):
        print(f"Instance size: {sys.getsizeof(part.content) / 1000000}MB")
        print(part.headers)

        print(f"Saving instance {index + 1} of {len(multipart_data.parts)}")
        # instances list from series API is in same order as multi-part form
        instance_path = series_path / Path(f"{instances[index]['instance_id']}.dcm")

        # trims off non-dicom portion of response body
        trimmed_response_content = part.content #[112:]

        with open(instance_path, mode='wb') as file:     
            file.write(trimmed_response_content)

    print(f"Total series size: {sys.getsizeof(response.content) / 1000000}MB")

    

def print_items(items: dict):
    for item in items:
        print("\n")
        for code in item:
            try:
                value = CODE_MAP[code]
            except KeyError:
                value = code
            print(f"{value}: {item[code]['Value']}")

def prompt_user_for_studies(studies):
    """
    Prompt the user to pick one of the studies given

    TODO: Allow user to pick more than one study
    """
    print("Options:")
    for index, _ in enumerate(studies):
        print(f"[{index}]: {studies[index]['patient_id']}")

    value = click.prompt(f'Choose a study to download ({0} - {len(studies) - 1})', type=int)
    if value < 0 or value > len(studies) - 1:
        print("Invalid option")
        sys.exit()
    chosen_study = studies[value]
    
    return [chosen_study]

def get_download_config(download_config):
    """
    Move ;
    Pick the studies that match the study_name and regex pattern from download_config
    """

    if not download_config: 
        print('No download config file providing - checking current directory for "downloader_config.yaml"')
        download_config = 'downloader_config.yaml'
        
    with open(download_config) as file:
        try:
            config = safe_load(file)
            
            return config
        except YAMLError as ye:
            raise YAMLError(ye)
        except KeyError:
            raise KeyError("Did not profile for provided study name")

def download_study(chosen_study, auth, fetch_date, out_dir, interactive=False, cache_file="cache.txt"):
    print(f"Processing study: {chosen_study['patient_id']}")
    
    series = get_series_by_study_and_date(chosen_study["study_id"], auth, fetch_date=fetch_date)

    for index, series_item in enumerate(series):
        print(f"[{index}]: {series[index]['series_description']}")
    print(f"[{len(series)}]: ALL SERIES")

    # If running interactive, have user pick series to download, or all
    series_to_process = []
    if interactive:
        value = click.prompt(f'Choose a series to download ({0} - {len(series)})', type=int)
        if value < 0 or value > len(series):
            print("Invalid option")
            sys.exit()  
        # if a single series was chosen
        if value < len(series):
            series_to_process.append(series[value])
        else:
            series_to_process += series
    else:
        series_to_process += series

    try:
        study_name = chosen_study['subject_id']
    except KeyError:
        study_name = chosen_study['patient_id']

    
    study_path = Path(study_name)
    if out_dir:
        study_path = Path(out_dir) / study_path
    study_path.mkdir(exist_ok=True, parents=True)

    skip_list = []
    cache_file = Path(cache_file)

    if cache_file.exists():
        with open(cache_file, 'r') as cache:
            for line in cache.readlines():
                skip_list.append(line.replace('\n', ""))

    with open(cache_file, 'a') as cache:
        for series_item in series_to_process:
            if series_item['series_description'] not in skip_list:
                series_path = Path(study_path / f"{series_item['series_number']}_{series_item['series_description']}")

                series_path.mkdir(exist_ok=True)

                instances = get_instances_by_study_series(chosen_study["study_id"], series_item["series_id"], auth)

                print(f"Downloading series: {series_item['series_description']}")
    
                download_instances(chosen_study["study_id"], series_item['series_id'], instances, series_path, auth)

                cache.write(series_item['series_description'])


def get_studies(fetch_date, auth_file, download_config, out_dir):
    """
    This method drives the download process from the CLI interactively, or from
    the download_configuration, if provided
    """

    # Take today's date if one is not provided through CLI
    if fetch_date is None:
        fetch_date = date.today()
    else:
        fetch_date = datetime.strptime(fetch_date, "%Y-%m-%d")

    # Setup basic auth from provided auth yaml file
    auth = get_auth(auth_file=auth_file)
    # Initial query to get list of studies on given date
    studies = get_studies_by_date(auth, fetch_date=fetch_date)

    # Only proceed if we found studies for given date
    if studies:
        studies_to_download = []
        interactive = False

        # yaml-driven
        if download_config:
            # Grab regex patterns from yaml
            download_config = get_download_config(download_config)
            patient_id_pattern = download_config['patient_id_pattern']
            patient_subject_id_pattern = download_config['patient_subject_id_pattern']

            # Go through the studies from given date and see if any match the pattern
            for study in studies:
                is_match = re.match(patient_id_pattern, study['patient_id'])
                if is_match:
                    studies_to_download.append(study)
                    if patient_subject_id_pattern:
                        study['subject_id'] = str(re.match(patient_subject_id_pattern, study['patient_id'])[0])
            
        # Interactive?
        else:
            studies_to_download = prompt_user_for_studies(studies)
            interactive = True

        # Now the we finally download the studies
        for study in studies_to_download:
            download_study(study, auth, fetch_date, out_dir, interactive=interactive)
        
    else:
        print("No studies found for this date")

@click.command()
@click.option('--fetch_date', '-d')
@click.option('--auth_file', '-a')  
@click.option('--download_config', '-c')
@click.option('--out_dir', '-o')
def get_studies_cli(fetch_date, auth_file, download_config, out_dir):
    get_studies(fetch_date, auth_file, download_config, out_dir)

if __name__ == '__main__':
    get_studies_cli()