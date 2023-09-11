.PHONY: check clean dev dist distclean production test

# Make requirements
requirements.txt: requirements.in
	pip-compile requirements.in

requirements-dev.txt: requirements-dev.in requirements.txt
	pip-compile requirements-dev.in

check:
	@which pip-compile > /dev/null

clean: check
	rm -f requirements.txt requirements-dev.txt

dev:
	rm -f requirements.txt requirements-dev.txt
	pip-compile requirements.in
	pip-compile requirements-dev.in
	pip-sync requirements.txt requirements-dev.txt

dist: distclean
	python -m build

distclean:
	rm -Rf dist link_sync.egg-info

production:
	rm -f requirements.txt
	pip-compile requirements.in
	pip-sync requirements.txt

lint:
	flake8

test:
	coverage run -m pytest && coverage report -m
