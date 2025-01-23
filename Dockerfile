FROM python:3.9-slim-bookworm

WORKDIR /opt/unreddit

COPY Pipfile .

RUN pip install pipenv && \
    pipenv install

COPY . .

CMD ["pipenv", "run", "main"]
