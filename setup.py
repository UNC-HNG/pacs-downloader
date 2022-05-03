from setuptools import setup, find_packages

setup(name='pacs-sdk',
      version='1.0.9',
      description='An SDK and CLI for downloading image data from PACS.',
      url='https://github.com/UNC-HNG/pacs-downloader',
      author='Maintainer: Will Asciutto',
      author_email='wasciutto@unc.edu',
      license='MIT',
      python_requires='>=3.6',
      include_package_data=True,
      packages=find_packages(),
      install_requires=['certifi>=2021.10.8',
                        'charset-normalizer>=2.0.10',
                        'click>=8.0.3',
                        'idna>=3.3',
                        'pydicom>=2.2.2',
                        'PyYAML>=6.0',
                        'requests>=2.27.1',
                        'requests-toolbelt>=0.9.1',
                        'urllib3>=1.26.7'],
      entry_points='''
      [console_scripts]
      pacs_downloader=pacs_sdk.image_downloader:get_studies_cli
      ''',
      zip_safe=False
      )
