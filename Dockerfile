FROM python:3.9

WORKDIR /app

COPY . /app

RUN pip3 install -r requirements.txt

CMD ["supervisord", "-c", "supervisord.conf", "-n"]

#ENTRYPOINT ["python"]

#CMD ["echo_server.py"]

