FROM --platform=linux/amd64 609067598877.dkr.ecr.us-east-1.amazonaws.com/devops/python:3.11.10
USER root
WORKDIR /whl
RUN pip install --upgrade splight-runner

ENV PYTHONUNBUFFERED=1

WORKDIR /code

RUN apt update --fix-missing && \
  apt install -y gcc

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
ENV PROCESS_TYPE="agent"
ENTRYPOINT [ "splight-runner", "run-agent" ]
