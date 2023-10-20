FROM python:3.11

ENV PYTHONUNBUFFERED=1

WORKDIR /code

RUN apt update --fix-missing

RUN pip install --upgrade pip && pip install poetry==1.5.1

# INSTALL AWS CLI
RUN pip install awscli

# Install docker
COPY install_docker.sh /code
RUN ./install_docker.sh

# Copy only requirements to cache them in docker layer
COPY poetry.lock pyproject.toml /code/
COPY . /code

# Install poetry dependencies
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi

WORKDIR /code/src
ENTRYPOINT [ "splight-agent" ]