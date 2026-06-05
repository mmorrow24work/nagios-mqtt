FROM jasonrivers/nagios:latest

RUN a2enmod auth_form session session_cookie request

COPY apache-nagios.conf /etc/apache2/sites-available/nagios.conf
COPY login.html /opt/nagios/share/login.html
