all: docs

run-debug-server:
	HTTPKOM_SETTINGS=../configs/debug.cfg ./runserver.py

docs: docs-html

docs-html:
	make -C docs html
	cp -r ./docs/_build/html/* ./gh-pages/html/

pyflakes:
	pyflakes ./httpkom

#test: pyflakes
#	py.test ./tests

.PHONY: all run-debug-server docs docs-html pyflakes