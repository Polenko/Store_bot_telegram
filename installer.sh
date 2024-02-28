#!/bin/bash

# Установка Python
python_version=3.11.6

sudo apt update
sudo apt install -y python$python_version python$python_version-dev python$python_version-distutils

# Установка pip
sudo apt install -y python$python_version-pip

# Установка библиотек Python из requirements.txt
sudo pip$python_version install -r requirements.txt

echo "Установка завершена."