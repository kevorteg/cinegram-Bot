@echo off
title CineGram Admin Panel
cd admin
echo Intentando instalar Flask si no existe...
pip install flask flask-cors
echo Iniciando Servidor de Panel de Control...
python app.py
pause
