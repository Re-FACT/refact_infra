# 
# Top Makefile
# ============
# 
# This is the top-level makefile of the project
# 
SHELL = bash
PYTHON_EXEC ?= python3
PYTHON_SCRIPT = ${PWD}/../../scripts/compress_bitstream.py
PYTHON_SCRIPT_MD5 = ${PWD}/../../scripts/bitstream_md5.py
TAR_FORMAT_POSIX = PAX_FORMAT
TAR_FORMAT_GNU = GNU_FORMAT
POSIX_COMPRESS_EXAMPLE_DIR = example_posix
POSIX_UNCOMPRESS_EXAMPLE_DIR = example_posix
GNU_COMPRESS_EXAMPLE_DIR = example_gnu
GNU_UNCOMPRESS_EXAMPLE_DIR = example_gnu
GZIP_COMPRESS_EXAMPLE_DIR = example_gzip
GZIP_UNCOMPRESS_EXAMPLE_DIR = example_gzip

.SILENT:

# Put it first so that "make" without argument is like "make help".
export COMMENT_EXTRACT

# Put it first so that "make" without argument is like "make help".
help:
	@${PYTHON_EXEC} -c "$$COMMENT_EXTRACT"

test_decompress_posix_format:
# This command runs a quick test on decompress on POSIX file format
	echo "======== Check md5 on the compressed copy ========"; \
	currDir=$${PWD} && cd ${POSIX_UNCOMPRESS_EXAMPLE_DIR} && ${PYTHON_EXEC} ${PYTHON_SCRIPT_MD5} --check_md5 --md5_file bitstream_posix_md5.yaml && cd $${currDir} || exit 1;
	echo "======== Test decompress on POSIX format ========"; \
	currDir=$${PWD} && cd ${POSIX_UNCOMPRESS_EXAMPLE_DIR} && ${PYTHON_EXEC} ${PYTHON_SCRIPT} --root_dir . --uncompress --tarfile_format ${TAR_FORMAT_POSIX} --file_list compressed_bitfile_posix.yaml  && cd $${currDir} || exit 1;

test_compress_posix_format: test_decompress_posix_format
# This command runs a quick test on compress on POSIX file format
	echo "======== Test compress on POSIX format ========"; \
	cp ${POSIX_COMPRESS_EXAMPLE_DIR}/fabric_bitstream.xml ${POSIX_COMPRESS_EXAMPLE_DIR}/fabric_bitstream.xml2zip || exit 1; 
	currDir=$${PWD} && cd ${POSIX_COMPRESS_EXAMPLE_DIR} && ${PYTHON_EXEC} ${PYTHON_SCRIPT} --root_dir . --compress --bitstream_file_postfix .xml2zip --tarfile_format ${TAR_FORMAT_POSIX} --file_list new_compressed_bitfile_posix.yaml || exit 1;
	echo "======== Create md5 ========"; \
	currDir=$${PWD} && cd ${POSIX_COMPRESS_EXAMPLE_DIR} && ${PYTHON_EXEC} ${PYTHON_SCRIPT_MD5} --create_md5 --root_dir . --md5_file new_bitstream_posix_md5.yaml && cd $${currDir} || exit 1;

test_decompress_gnu_format:
# This command runs a quick test on decompress on GNU file format
	echo "======== Check md5 on the compressed copy ========"; \
	currDir=$${PWD} && cd ${GNU_UNCOMPRESS_EXAMPLE_DIR} && ${PYTHON_EXEC} ${PYTHON_SCRIPT_MD5} --check_md5 --md5_file bitstream_gnu_md5.yaml && cd $${currDir} || exit 1;
	echo "======== Test decompress on GNU format ========"; \
	currDir=$${PWD} && cd ${GNU_UNCOMPRESS_EXAMPLE_DIR} && ${PYTHON_EXEC} ${PYTHON_SCRIPT} --root_dir . --uncompress --tarfile_format ${TAR_FORMAT_GNU}  --file_list compressed_bitfile_gnu.yaml  && cd $${currDir} || exit 1;

test_compress_gnu_format: test_decompress_gnu_format
# This command runs a quick test on decompress on GNU file format
	echo "======== Test compress on GNU format ========"; \
	cp ${GNU_COMPRESS_EXAMPLE_DIR}/fabric_bitstream.xml ${GNU_COMPRESS_EXAMPLE_DIR}/fabric_bitstream.xml2zip || exit 1; 
	currDir=$${PWD} && cd ${GNU_COMPRESS_EXAMPLE_DIR} && ${PYTHON_EXEC} ${PYTHON_SCRIPT} --root_dir . --compress  --bitstream_file_postfix .xml2zip --file_list new_compressed_bitfile_gnu.yaml && cd $${currDir} || exit 1;
	echo "======== Create md5 ========"; \
	currDir=$${PWD} && cd ${GNU_COMPRESS_EXAMPLE_DIR} && ${PYTHON_EXEC} ${PYTHON_SCRIPT_MD5} --create_md5 --root_dir . --md5_file new_bitstream_gnu_md5.yaml && cd $${currDir} || exit 1;

test_decompress_gzip_format:
# This command runs a quick test on decompress on gzip format
	echo "======== Check md5 on the compressed copy ========"; \
	currDir=$${PWD} && cd ${GZIP_UNCOMPRESS_EXAMPLE_DIR} && ${PYTHON_EXEC} ${PYTHON_SCRIPT_MD5} --check_md5 --md5_file bitstream_gzip_md5.yaml && cd $${currDir} || exit 1;
	echo "======== Test decompress on gzip format ========"; \
	currDir=$${PWD} && cd ${GZIP_UNCOMPRESS_EXAMPLE_DIR} && ${PYTHON_EXEC} ${PYTHON_SCRIPT} --root_dir . --uncompress --gzip_only --file_list compressed_bitfile_gzip.yaml && cd $${currDir} || exit 1;

test_compress_gzip_format: test_decompress_gzip_format
# This command runs a quick test on decompress on gzip format
	echo "======== Test compress on gzip format ========"; \
	cp ${GZIP_COMPRESS_EXAMPLE_DIR}/fabric_bitstream.xml ${GZIP_COMPRESS_EXAMPLE_DIR}/fabric_bitstream.xml2zip || exit 1; 
	currDir=$${PWD} && cd ${GZIP_COMPRESS_EXAMPLE_DIR} && ${PYTHON_EXEC} ${PYTHON_SCRIPT} --root_dir . --compress  --bitstream_file_postfix .xml2zip --gzip_only --file_list new_compressed_bitfile_gzip.yaml && cd $${currDir} || exit 1;
	echo "======== Create md5 ========"; \
	currDir=$${PWD} && cd ${GZIP_COMPRESS_EXAMPLE_DIR} && ${PYTHON_EXEC} ${PYTHON_SCRIPT_MD5} --create_md5 --root_dir . --md5_file new_bitstream_gzip_md5.yaml && cd $${currDir} || exit 1;


all:
	make test_compress_posix_format
	make test_compress_gnu_format
	make test_compress_gzip_format
# Run all the test one by one

clean:
# This command removes all the intermediate files during compression
	echo "======== Remove all the outputs ========"; \
	rm -rf new_bitstream_*_md5.yaml
	rm -rf example*/*.xml

# Functions to extract comments from Makefiles
define COMMENT_EXTRACT
import re
with open ('Makefile', 'r' ) as f:
    matches = re.finditer('^([a-zA-Z-_]*):.*\n#(.*)', f.read(), flags=re.M)
    for _, match in enumerate(matches, start=1):
        header, content = match[1], match[2]
        print(f"  {header:10} {content}")
endef
