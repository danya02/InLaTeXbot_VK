FROM python:3.9

COPY src/ /
COPY requirements.txt /
RUN pip3 install --no-cache -r requirements.txt

WORKDIR /src

ENTRYPOINT ["gunicorn", "-w", "4", "main:app"]
