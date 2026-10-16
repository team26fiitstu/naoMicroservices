FROM python:3.12-slim
COPY ./server /python-flask

COPY ./requirements.txt /python-flask

WORKDIR /python-flask

RUN apt-get -y update

RUN apt-get install -y wget ffmpeg libsm6 libxext6 libgl1

RUN pip install --timeout 120 --retries 5 -r requirements.txt

RUN wget https://github.com/WongKinYiu/yolov7/releases/download/v0.1/yolov7-w6-pose.pt

ENV NO_NAMING $NO_NAMING

CMD [ "python", "server.py" ]