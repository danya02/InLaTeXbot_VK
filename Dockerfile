FROM danya02/raspberry-pi-texlive-full:latest


FROM python:3.9

ADD --from=0 /usr/share/tex* /usr/share/
RUN rm -rf /usr/share/texmf/doc
ADD --from=0 /etc/texmf /etc/
ADD --from=0 /var/lib/tex* /var/lib/
ADD --from=0 /usr/share/latex* /usr/share
ADD --from=0 /usr/share/fonts* /usr/share

COPY src/ /
COPY requirements.txt /

RUN pip3 install --no-cache -r requirements.txt

WORKDIR /src

ENTRYPOINT ["gunicorn", "-w", "4", "main:app"]
