# -*- makefile-gmake -*-
#
# Copyright (C) 2014 Craig Hobbs
#

PACKAGE_NAME = mrpypi
PACKAGE_TESTS = $(PACKAGE_NAME)/tests

# Local directories
ENV = .env
COVER = .cover
PYFLAKES = .pyflakes

# Python version support
PYTHON_VERSIONS = \
    2.7 \
    2.6 \
    3.2 \
    3.3 \
    3.4

# Help
.PHONY: help
help:
	@echo "usage: make [test|pyflakes|cover|check|clean|superclean]"

# Run unit tests
.PHONY: test
test: pyflakes test_$(firstword $(PYTHON_VERSIONS))

# Pre-checkin check
.PHONY: check
check: pyflakes clean $(foreach V, $(PYTHON_VERSIONS), test_$(V)) cover

# Clean
.PHONY: clean
clean:
	-rm -rf \
		$$(find $(PACKAGE_NAME) -name '__pycache__') \
		$$(find $(PACKAGE_NAME) -name '*.pyc') \
		build \
		dist \
		*.egg-info \
		.coverage \
		$(COVER)

# Superclean
.PHONY: superclean
superclean: clean
	-rm -rf $(ENV)

# Setup
.PHONY: setup
setup:
	sudo add-apt-repository -y ppa:fkrull/deadsnakes
	sudo apt-get update
	sudo apt-get install -y \
		python-pip \
		python-virtualenv \
		$(foreach P, $(PYTHON_VERSIONS),$(if $(shell which python$P),,python$P))
	pip install -U pip virtualenv

# Macro to generate virtualenv rules - env_name, python_version, packages, commands
define ENV_RULE
$(ENV)/$(strip $(1)):
	virtualenv -p python$(strip $(2)) $$@
	$(if $(strip $(3)), . $$@/bin/activate && pip install $(3))

.PHONY: $(1)
$(1): $(ENV)/$(strip $(1))
	$(4)
endef

# Generate test rules
define TEST_COMMANDS
	. $$</bin/activate && python setup.py test
endef
$(foreach V, $(PYTHON_VERSIONS), $(eval $(call ENV_RULE, test_$(V), $(V), , $(TEST_COMMANDS))))

# Generate coverage rule
define COVER_COMMANDS
	. $$</bin/activate && \
		coverage run --branch --source $(PACKAGE_NAME) setup.py test && \
		coverage html -d $(COVER) && \
		coverage report
	@echo
	@echo Coverage report is $(COVER)/index.html
endef
$(eval $(call ENV_RULE, cover, $(firstword $(PYTHON_VERSIONS)), coverage, $(COVER_COMMANDS)))

# Generate pyflakes rule
define PYFLAKES_COMMANDS
	. $$</bin/activate && pyflakes ./$(PACKAGE_NAME)
endef
$(eval $(call ENV_RULE, pyflakes, $(firstword $(PYTHON_VERSIONS)), pyflakes, $(PYFLAKES_COMMANDS)))
