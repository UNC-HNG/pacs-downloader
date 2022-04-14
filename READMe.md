### PACS Downloader

#### Install

`pip install git+https://github.com/UNC-HNG/pacs-downloader.git`

#### Create your credentials file
Create a credentials file by copying the contents of `pacs_credentials_template.yaml` into your own .yaml file. Fill out your PACS username and password. Make sure you save this file in a secure location or lock down its read permission to protect your password.

```
username:
password:
```

#### Run the command line tool

```
pacs_downloader --help
Usage: pacs_downloader [OPTIONS]

Options:
  -d, --fetch_date TEXT       Use to choose a date to search for data to
                              download. Defaults to current day.  [required]
  -a, --auth_file TEXT        A .yaml file containing your PACS credentials.
                              See the project README for help setting this up.
                              [required]
  -c, --download_config TEXT  A .yaml file which helps specify which studies
                              to download.
  -o, --out_dir TEXT          Where to save the image data - defaults to
                              current directory.
  --help                      Show this message and exit.
```

If you do not specify a download_config file, the pacs_downloader will run in interactive mode, letting you manually choose which data to download.

To run the pacs_downloader in an automated fashion, you can create a download configuration file to specify which studies to download with a regex:

```
patient_id_pattern: ^MyStudy [0-9]{6}$
patient_subject_id_pattern: [0-9]{6}
```

`patient_id_pattern` will let you pick a patient by their patient id, which will often follow a pattern unique to a study. `patient_subject_id_pattern` simply indicates which portion of the `patient_id_pattern` is the subject id, and will name your output folder after this id (not required)