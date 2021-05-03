#FROM python:3.9
FROM python:3.9-buster

#COPY --from=danya02/raspberry-pi-texlive-full:latest /usr/share/tex* /usr/share/
#RUN rm -rf /usr/share/texmf/doc
#COPY --from=danya02/raspberry-pi-texlive-full:latest /etc/texmf /etc/
#COPY --from=danya02/raspberry-pi-texlive-full:latest /var/lib/tex* /var/lib/
#COPY --from=danya02/raspberry-pi-texlive-full:latest /usr/share/latex* /usr/share
#COPY --from=danya02/raspberry-pi-texlive-full:latest /usr/share/fonts* /usr/share/
#COPY --from=danya02/raspberry-pi-texlive-full:latest /usr/bin/* /usr/bin/

RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y texlive-full
RUN apt-get clean
RUN rm -rf /usr/share/texmf/doc

RUN mkdir /build
ADD renderer_src/requirements.txt /
RUN pip3 install -r requirements.txt
ADD renderer_src/* /

ENTRYPOINT celery -A latex_celery_tasks:cel worker --loglevel INFO 
