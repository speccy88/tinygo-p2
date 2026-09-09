PYTHON ?= python3
.PHONY: host-test preflight fetch fetch-go llvm backend-control libraries loader probe baseline firmware ports evidence
host-test:
	$(PYTHON) scripts/host_check.py
preflight fetch fetch-go llvm backend-control libraries loader probe ports evidence:
	$(PYTHON) scripts/project.py $@
baseline:
	$(PYTHON) scripts/project.py firmware --mode c
firmware:
	$(PYTHON) scripts/project.py firmware --mode go
# Hardware actions are intentionally NOT part of 'all', 'test', or any build rule.
# Run scripts/project.py hil explicitly with an exact port and --allow-ram-reset.

.PHONY: probe-full
probe-full:
	$(PYTHON) scripts/project.py probe --stage full
