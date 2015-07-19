override PACKAGE_NAME := mrpypi
$(shell if [ ! -f .makefile ]; then $(if $(findstring Darwin,$(shell uname)),curl -o,wget -O) .makefile 'https://raw.githubusercontent.com/craigahobbs/chisel/master/Makefile'; fi)
include .makefile
