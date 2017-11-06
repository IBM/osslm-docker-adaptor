# Docker Resource Manager in a box

## Overview

Docker based Resource Manager to facilitate demonstrations on a single laptop and how to wrap software resources or other management software with the resource manager lifecycle API. This reference implementation is built directly on Docker and is intended to demonstrate the Resource Manager concepts, not for any production use. 

## Getting Started

### Install
* Install Docker as per instructions for your environment at [https://www.docker.com/]
* Copy Docker Resource Manager to __\<RM_HOME\>__

Docker toolbox or native docker installation on Linux is supported only.

### Start Docker Resource Manager

To build the base image required to deploy Resources, run the following command in the __\<RM_HOME\>__ directory.

```
docker-compose -f rm-base.yml build
```

To start the docker resource manager on a linux host running the docker daemon locally, run the following command in __\<RM_HOME\>__:

```
docker-compose -f rm-local.yml up -d docker-rm
```

If you are running docker on a remote docker machine, e.g. Docker Toolbox on windows or Mac, you should use rm-remote.yml, i.e.

```
docker-compose -f rm-remote.yml up -d docker-rm
```

Edit rm-remote.yml to reflect your environment, as below

```
version: '3'
services:
  docker-rm:
    build: ./docker-rm
    ports:
    - "8081:8081"
    volumes:
    - <your-home-dir>.docker/machine/machines/default:/opt/dockercerts
    - ./opt/rm/config:/opt/rm/config
    - ./opt/rm/logs:/opt/rm/logs
    - ./opt/csars:/opt/rm/csars
    environment:
    - DOCKER_HOST=tcp://<address-of-remote-docker-machine>
    - DOCKER_TLS_VERIFY=1
    - DOCKER_CERT_PATH=/opt/dockercerts
    - DOCKER_MACHINE_NAME=default
```
Once running, docker resource manager logs can be found at __\<RMDIR\>/opt/rm/logs__

You can check all is well by running the following:

```
tail -f <RM_HOME>/opt/rm/logs/info.log
```

#### Quick start to add user defined Resources

The resource manager will look for Resource directories in a pre-configured location on start up. The resource manager expects each Resource directory to contain the following:
* _**Dockerfile**_: CSARs must be based on the _**baseimage**_ docker image. The docker resource manager expects the name of the CSAR image to be the same as the name its parent directory. Dockerfiles must contain steps to add lifecycle and operation directories to /opt and any CSAR specific steps to copy/install software to support the lifecycle transitions and operations.
* _**resource.yml**_: Resource properties, supported lifecycle transitions and operations
* _**lifecycle**_: Directory containing the software that implements each lifecycle transition
* _**operations**_: Directory containing the software that implements each operation
* _**software**_: Any Resource specific software

Resource directories can be added to the resource manager as follows:
* Copy Resource directories directly to the __\<RMDIR\>/opt/csars__ directory and restart the resource manager. 
* Mount a directory containing Resources into the resource manager container.

Check out the documentation in the docs directory1 to find out more about how to build and onboard Resources to the Docker Resource Manager.

### Run Resource Manager Swagger UI

To check that all is working log onto the resource manager UI at http://localhost:8081/ui (replace localhost with your docker installation ip address, e.g. 192.168.99.100 for docker toolbox)


