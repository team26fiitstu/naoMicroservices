ARG UBUNTU_VERSION=14.04
FROM ubuntu:$UBUNTU_VERSION

ARG PYTHON_VERSION=2.7.5

# Install dependencies
# PIP - openssl version > 1.1 may be an issue (try older ubuntu images)
RUN apt-get update \
  && apt-get install -y wget python-pip python2.7-dev gcc make openssl libffi-dev libgdbm-dev libsqlite3-dev libssl-dev zlib1g-dev \
  && apt-get clean

WORKDIR /tmp/


RUN mkdir pynaoqi
COPY ./pynaoqi /pynaoqi
#COPY ./pynaoqi /usr/local/lib/python2.7/
COPY . /naoRobotAPI
ENV PYTHONPATH=${PYTHONPATH}:/pynaoqi

WORKDIR /naoRobotAPI
RUN ./.bashrc
#RUN apt-get -y update
RUN apt-get install -y python-simplegeneric

RUN pip install ./compatDep/Click-7.0-py2.py3-none-any.whl
RUN pip install ./compatDep/scandir-1.7.tar.gz
RUN pip install ./compatDep/typing-3.10.0.0-py2-none-any.whl
RUN pip install ./compatDep/ptyprocess-0.7.0-py2.py3-none-any.whl
RUN pip install ./compatDep/pexpect-4.9.0-py2.py3-none-any.whl
RUN pip install ./compatDep/pathlib2-2.3.7.post1-py2.py3-none-any.whl
RUN pip install ./compatDep/setuptools-40.4.2-py2.py3-none-any.whl
RUN pip install ./compatDep/ipython_genutils-0.2.0-py2.py3-none-any.whl
RUN pip install ./compatDep/decorator-4.4.2-py2.py3-none-any.whl
RUN pip install ./compatDep/traitlets-4.0.0-py2.py3-none-any.whl
RUN pip install ./compatDep/pickleshare-0.7.5-py2.py3-none-any.whl
RUN pip install ./compatDep/python_dotenv-0.17.1-py2.py3-none-any.whl
RUN pip install ./compatDep/dotenv-0.9.9-py2.py3-none-any.whl
RUN pip install ./compatDep/ipython-4.1.0-py2-none-any.whl
RUN pip install ./compatDep/MarkupSafe-1.1.1.tar.gz
RUN pip install ./compatDep/Jinja2-2.11.3-py2.py3-none-any.whl
RUN pip install ./compatDep/itsdangerous-1.1.0-py2.py3-none-any.whl
RUN pip install ./compatDep/Werkzeug-1.0.1-py2.py3-none-any.whl
RUN pip install ./compatDep/Flask-1.1.1-py2.py3-none-any.whl
RUN pip install ./compatDep/Flask_Cors-3.0.3-py2.py3-none-any.whl
RUN pip install -r requirements.txt
#RUN python initialScript.py
#file:///C:/Program%20Files%20(x86)/Aldebaran%20Robotics/Choregraphe%20Suite%202.1/share/doc/getting_started/helloworld_choregraphe_script.html
#python robot_module_testing/movement_test.py
#file:///C:/Program%20Files%20(x86)/Aldebaran%20Robotics/Choregraphe%20Suite%202.1/share/doc/software/choregraphe/index.html
#RUN sudo apt install cmake
#python ./robot_module_testing/test.py

ENV NO_NAMING $NO_NAMING

CMD [ "python", "server.py" ]