FROM python:3.9

WORKDIR /app

COPY . /app

RUN pip3 install -r requirements.txt

ENTRYPOINT ["python"]

# вторым аргументов вставьте путь к конфигу
CMD ["main.py", "server_config/example_conf.yaml"]

