from setuptools import setup, find_packages

setup(name='pacs-sdk',
      version='0.0.0',
      description='An SDK for downloading image data from PACS.',
      author='Maintainer: Will Asciutto',
      author_email='wasciutto@unc.edu',
      license='MIT',
      python_requires='>=3.6',
      include_package_data=True,
      packages=find_packages(),
      install_requires=['certifi>=2021.10.8',
                        'charset-normalizer>=2.0.10'
                        'click>=8.0.3'
                        'idna>=3.3'
                        'pydicom>=2.2.2'
                        'PyYAML>=6.0'
                        'requests>=2.27.1'
                        'urllib3>=1.26.7'],
      entry_points='''
      [console_scripts]
      ''',
      zip_safe=False
      )