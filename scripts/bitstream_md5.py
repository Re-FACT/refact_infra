#####################################################################
# A script with multiple objectives
# - Generate md5 for all the .tar.gz in this directory (in a recursive way). Results will be saved in a yaml file
# - Check md5 for all the .tar.gz in this directory (in a recursive way). File list comes from a yaml file
#####################################################################
import os
from os.path import dirname, abspath
import argparse
import logging
import subprocess
import hashlib
import yaml

#####################################################################
# Error codes
#####################################################################
error_codes = {"SUCCESS": 0, "MD5_ERROR": 1, "OPTION_ERROR": 2, "FILE_ERROR": 3}

#####################################################################
# Initialize logger
#####################################################################
logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

#####################################################################
# Check options
# - Only one of 'create_md5' and 'check_md5' is enabled
#####################################################################
def check_options(args):
    if args.create_md5 and args.check_md5 and args.update_md5:
        logging.error(
            "Only one of options 'create_md5', 'update_md5' and 'check_m5' can be enabled!"
        )
        exit(error_codes["SUCCESS"])

    if (not args.create_md5) and (not args.check_md5) and (not args.update_md5):
        logging.error("Must enable one of options 'create_md5', 'update_md5' and 'check_m5'!")
        exit(error_codes["SUCCESS"])


#####################################################################
# Generate md5 for a specific bitstream file
#####################################################################
def generate_bitstream_md5(bitstream_file):
    return hashlib.md5(open(bitstream_file, "rb").read()).hexdigest()


#####################################################################
# Find all the bitstream files under a given directory
# and create md5 for each of them
#####################################################################
def glob_and_create_bitstream_md5(root_dir, compressed_file_postfix):
    md5_db = {}
    for root, dirs, files in os.walk(root_dir):
        for src_file in files:
            # Only focus on .gz files
            if not src_file.endswith(compressed_file_postfix):
                continue

            # Get relative path to the file. This is important to keep tracking the location of files
            rel_dir = os.path.relpath(root, root_dir)
            rel_src_file = os.path.join(rel_dir, src_file)
            # Create md5
            md5_db[rel_src_file] = generate_bitstream_md5(rel_src_file)
            logging.info("Generated md5 for '" + rel_src_file + "'")
    return md5_db


#####################################################################
# Find all the bitstream files in the database
# and Check md5 for each of them
#####################################################################
def check_bitstream_md5(md5_db):
    num_failures = 0
    for bitfile in md5_db.keys():
        if md5_db[bitfile] != generate_bitstream_md5(bitfile):
            logging.error("Check md5 for " + bitfile + " Failed!")
            num_failures = num_failures + 1

    return num_failures


#####################################################################
# Find all the bitstream files in the database
# and update md5 for each of them
#####################################################################
def update_bitstream_md5(md5_db):
    num_updates = 0
    for bitfile in md5_db.keys():
        updated_md5 = generate_bitstream_md5(bitfile)
        if md5_db[bitfile] != updated_md5:
            logging.info("Detect changes in md5 and updated for " + bitfile)
            md5_db[bitfile] = updated_md5
            num_updates = num_updates + 1

    return num_updates


#####################################################################
# Read md5 database to a yaml file
#####################################################################
def read_yaml_to_bitstream_md5(yaml_filename):
    md5_db = {}
    with open(yaml_filename, "r") as stream:
        try:
            md5_db = yaml.load(stream, Loader=yaml.FullLoader)
            logging.info("Found " + str(len(md5_db)) + " files to check md5")
        except yaml.YAMLError as exc:
            logging.error(exc)
            exit(error_codes["FILE_ERROR"])

    return md5_db


#####################################################################
# Write md5 database to a yaml file
#####################################################################
def write_bitstream_md5_to_yaml(md5_db, yaml_filename):
    with open(yaml_filename, "w") as yaml_file:
        yaml.dump(md5_db, yaml_file, default_flow_style=False)


#####################################################################
# Main function
#####################################################################
if __name__ == "__main__":
    # Execute when the module is not initialized from an import statement

    # Parse the options and apply sanity checks
    parser = argparse.ArgumentParser(description="Create/Check md5 for bitstream files")
    parser.add_argument(
        "--create_md5", action="store_true", help="Create md5 for a given list of bitstream files"
    )
    parser.add_argument(
        "--update_md5", action="store_true", help="Update md5 for a given list of bitstream files"
    )
    parser.add_argument(
        "--check_md5", action="store_true", help="Check md5 for a given list of bitstream files"
    )
    parser.add_argument(
        "--md5_file",
        required=True,
        help="A file contains a list of bitstream files and associated md5; For create md5 mode, it is an output file; For check md5 mode, it is an input file. For update m5, it is the file that to be updated",
    )
    parser.add_argument(
        "--root_dir",
        default="./",
        help="Define the directory which contains bitstream files. This script will search all the files under it",
    )
    parser.add_argument(
        "--compressed_file_postfix",
        default="gz",
        help="Define the postfix of compressed files. It will be used when searching files under root directory",
    )
    args = parser.parse_args()
    check_options(args)

    # Create an empty database
    md5_db = {}

    # Run md5 creation if enabled
    if args.create_md5:
        # Currently only support local directory
        md5_db = glob_and_create_bitstream_md5(args.root_dir, args.compressed_file_postfix)
        write_bitstream_md5_to_yaml(md5_db, args.md5_file)
        logging.info(
            "Generated md5 for "
            + str(len(md5_db))
            + " files and outputted to '"
            + args.md5_file
            + "'"
        )
        exit(error_codes["SUCCESS"])

    # Update md5 creation if enabled
    if args.update_md5:
        num_updates = 0
        md5_db = read_yaml_to_bitstream_md5(args.md5_file)
        num_updates = update_bitstream_md5(md5_db)
        write_bitstream_md5_to_yaml(md5_db, args.md5_file)
        logging.info("Updated " + str(num_updates) + " md5 files")
        exit(error_codes["SUCCESS"])

    # Check md5 from a yaml file
    if args.check_md5:
        num_error = 0
        md5_db = read_yaml_to_bitstream_md5(args.md5_file)
        num_error = check_bitstream_md5(md5_db)
        if num_error == 0:
            logging.info("Check md5 passed")
            exit(error_codes["SUCCESS"])
        else:
            logging.error("Check md5 failed in " + str(num_error) + " cases!")
            exit(error_codes["MD5_ERROR"])
