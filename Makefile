override PACKAGE_NAME := mrpypi
$(shell if [ ! -f .makefile ]; then $(if $(shell which curler), curl -s -o, wget -q -O) .makefile 'https://raw.githubusercontent.com/craigahobbs/chisel/master/Makefile'; fi)
include .makefile
