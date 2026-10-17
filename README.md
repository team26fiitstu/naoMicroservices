# Docker compose orchestration (without command API connected to LLM)

 - set resource location pointing to Docker Hub in .env file:  

```REGISTRY=jperdek```  

 - pull:

``` docker compose -f docker-compose.dev.yml pull```

 - run:  

```docker compose -f docker-compose.dev.yml up```  

 - [ALTERNATIVE] build and run:  

```docker compose -f docker-compose.dev.yml up --build```  


# Robot configuration

## Remote run
Set NAO_IP in ```./team-19-social-robot/naoRobotAPI/.env``` to robot IP (NAO robot should be on the same Wifi if not then configure it using ethernet cable):

```NAO_IP=10.62.44.100```
```NAO_PORT=9559```
```HOST_IP=127.0.0.1```
```HOST_PORT=1234```


## Local run (choregraphe)
Set NAO_IP in ```./team-19-social-robot/naoRobotAPI/.env``` to localhost

```NAO_IP=127.0.0.1```
```NAO_PORT=9559```
```HOST_IP=127.0.0.1```
```HOST_PORT=1234``` 



# Python Installation

### Python 2.7 (Windows Installation  NAO Robot API)

- 1. Download Python 2.7 (https://www.python.org/download/releases/2.7/)  
- 2. Install Python 2.7  
- 3. Download Nao python SDK from https://aldebaran.com/en/support/kb/nao6/downloads/nao6-software-downloads/ and extract it + add it to path (http://doc.aldebaran.com/2-5/dev/python/install_guide.html):  

```cd D:\originalRobotics\robot\robot```  


- 4. Set PYTHONPATH system environment variable (premenne prostredia - systemove):  

```PYTHONPATH``` ```C:\Program Files\pynaoqi\lib```  


- 5. Download wheel pip, wheel setuptools, and wheel files from https://pypi.org: https://pypi.org/project/pip/20.3.4/#files  
- 6. Run and install using Python2.7 and its pip:  

```"C:\Python27\python.exe" .\get-pip.py "pip-20.3.4-py2.py3-none-any.whl" "setuptools-44.0.0-py2.py3-none-any.whl" "wheel-0.37.0-py2.py3-none-any.whl"```  

```"C:\Python27\python.exe" -m pip install ./winDependencies/qi-1.8.3-cp27-none-win_amd64.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/almath-1.6.8-cp27-none-win_amd64.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/chardet-4.0.0-py2.py3-none-any.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/urllib3-1.26.3-py2.py3-none-any.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/idna-2.9-py2.py3-none-any.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/certifi-2020.6.20-py2.py3-none-any.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/requests-2.25.1-py2.py3-none-any.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/gTTS-token-1.1.4.tar.gz```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/click-7.1.2-py2.py3-none-any.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/six-1.15.0-py2.py3-none-any.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/backports.functools_lru_cache-1.6.1-py2.py3-none-any.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/soupsieve-1.9.6-py2.py3-none-any.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/beautifulsoup4-4.9.3-py2-none-any.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/gTTS-2.1.0-py2-none-any.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/numpy-1.16.1-cp27-cp27m-win32.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/python_dateutil-2.8.1-py2.py3-none-any.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/pytz-2019.3-py2.py3-none-any.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/pandas-0.23.3-cp27-cp27m-win_amd64.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/enum34-1.1.10-py2-none-any.whl```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/pathlib-1.0.1.tar.gz```  
```"C:\Python27\python.exe" -m pip install ./winDependencies/pyzbar-0.1.7-py2.py3-none-win_amd64.whl```  
 

- 7. Run microservice to command NAO:  

```"C:\Python27\python.exe" D:\tpVideoKonverter\team-19-social-robot\naoRobotAPI\server.py```  



### Python 3.xxx

- 1. Download Python 3.11 (https://www.python.org/downloads/release/python-3110/)    
- 2. Install Python 3.11  
- 3. Create Venv or run it globally  
- 4. Move to skeletonFinderAPI directory:  

    ```D:\tpVideoKonverter\team-19-social-robot\skeletonFinderAPI```  


- 5. Install dependencies:  

    ```"D:\tpVideoKonverter\team-19-social-robot\skeletonFinderAPI\.venv\Scripts\python.exe" -m pip install -r requirements.txt```  


- 6. Run:  

    ```"D:\tpVideoKonverter\team-19-social-robot\skeletonFinderAPI\.venv\Scripts\python.exe" D:\tpVideoKonverter\team-19-social-robot\skeletonFinderAPI\server\server.py```  




# Run
It is necessary to use only one python from Python 2.7 and 3.xxx as can be seen:  


## Microservices  

### Identification of the pose from the image  
```cd D:\tpVideoKonverter```  
```"D:\tpVideoKonverter\team-19-social-robot\skeletonFinderAPI\.venv\Scripts\python.exe" D:\tpVideoKonverter\team-19-social-robot\skeletonFinderAPI\server\server.py```  

### Managing the information about the pose  
```cd D:\tpVideoKonverter```  
```"D:\tpVideoKonverter\team-19-social-robot\skeletonFinderAPI\.venv\Scripts\python.exe" "D:\tpVideoKonverter\team-19-social-robot\translator\nao_pose_service.py```  

### Managing commands conversion via generative model API (needs subsciption - not necessary)  
```cd D:\tpVideoKonverter```
```"D:\tpVideoKonverter\team-19-social-robot\skeletonFinderAPI\.venv\Scripts\python.exe" "D:\tpVideoKonverter\team-19-social-robot\voiceCommandAPI\server.py"```

### Storing data to dedicated space such as disc  
```cd D:\tpVideoKonverter```
```"D:\tpVideoKonverter\team-19-social-robot\skeletonFinderAPI\.venv\Scripts\python.exe"  D:\tpVideoKonverter\team-19-social-robot\exerciseConfigService\run.py```  

### Robust third party service to convert audio and video to text 
```cd D:\tpVideoKonverter```  
```"D:\tpVideoKonverter\team-19-social-robot\audioToTextConverter\.venv\Scripts\python.exe" "D:\tpVideoKonverter\team-19-social-robot\audioToTextConverter\text_from_audio_extractor_service.py```  
  
### Frontend - integrating collaboration into one  
```cd D:\tpVideoKonverter\team-19-social-robot\naoRobotAPI```  
```"C:\Python27\python.exe" D:\tpVideoKonverter\team-19-social-robot\naoRobotAPI\server.py```  

No all microservices are always necessary. Save resources.  


## Dedicated disk location
Depends on the disk where you run ```D:\tpVideoKonverter\team-19-social-robot\exerciseConfigService```.

Located at: ```/service/exercises``` such as ```D:\service\exercises``` on disk ```D```  



