override PACKAGE_NAME := mrpypi
$(shell if [ ! -f .makefile ]; then $(if $(shell which curl), curl -s -o, wget -q -O) .makefile 'https://raw.githubusercontent.com/craigahobbs/chisel/master/Makefile'; fi)
include .makefile

# Add additional help
help:
	@echo "       make [run]"

# Run a local mrpypi
define RUN_COMMANDS_FN
	$(2) -m mrpypi $(ARGS)
endef
$(eval $(call ENV_RULE, run, -e ., RUN_COMMANDS_FN))
