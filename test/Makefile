# 
# Top Makefile
# ============
# 
# This is the top-level makefile of the project
# 
SHELL = bash
PYTHON_EXEC ?= python3

.SILENT:

# Put it first so that "make" without argument is like "make help".
export COMMENT_EXTRACT

# Put it first so that "make" without argument is like "make help".
help:
	@${PYTHON_EXEC} -c "$$COMMENT_EXTRACT"

all:
# This command runs a full set of regression test
	echo "======== Run regression test for check_openfpga_version ========"; \
	currDir=$${PWD} && cd file_compression && make all && cd $${currDir} || exit 1;

# Functions to extract comments from Makefiles
define COMMENT_EXTRACT
import re
with open ('Makefile', 'r' ) as f:
    matches = re.finditer('^([a-zA-Z-_]*):.*\n#(.*)', f.read(), flags=re.M)
    for _, match in enumerate(matches, start=1):
        header, content = match[1], match[2]
        print(f"  {header:10} {content}")
endef
