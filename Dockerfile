FROM python:3.7-slim-buster

RUN apt-get -q update && \
    apt-get -yq install build-essential

COPY Pipfile /opt/unreddit/

WORKDIR /opt/unreddit

RUN pip install pipenv && \
    pipenv install

COPY . /opt/unreddit

CMD ["pipenv", "run", "main"]
