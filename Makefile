PYTHON ?= python

.PHONY: install test eval demo check
install:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install --no-deps -e .
test:
	$(PYTHON) -m unittest discover -s tests -v
eval:
	$(PYTHON) eval.py
demo:
	$(PYTHON) -m docguard extract data/documents/01_invoice.txt
check: test eval
