FROM python:3.9-slim-bookworm

RUN apt-get -q update && \
    apt-get -yq install build-essential

COPY Pipfile /opt/unreddit/

WORKDIR /opt/unreddit

RUN pip install pipenv && \
    pipenv install

COPY . /opt/unreddit

CMD ["pipenv", "run", "main"]
