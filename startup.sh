#!/bin/sh
cd /home/site/wwwroot
gunicorn --bind=0.0.0.0:8000 --timeout 600 app:app
