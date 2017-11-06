FROM dockerrm_baseimage

RUN mkdir /opt/rm
WORKDIR /opt/rm

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r ./requirements.txt

COPY . .

ENTRYPOINT ["python3", "/opt/rm/app.py"]
