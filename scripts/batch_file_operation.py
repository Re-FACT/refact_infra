#####################################################################
# A script to create symbolic links with a given configuration file
#####################################################################
import os
from os.path import dirname, abspath
import argparse
import logging
import subprocess
import hashlib
import yaml
import shutil

#####################################################################
# Error codes
#####################################################################
error_codes = {"SUCCESS": 0, "ERROR": 1, "OPTION_ERROR": 2, "FILE_ERROR": 3}

# Maximum file name to show in log files
max_filename_len = 40

#####################################################################
# Initialize logger
#####################################################################
logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)


#####################################################################
# Check and validate options
#####################################################################
def check_options(args):
    if args.operation != "link" and args.operation != "copy":
        logging.error("Invalid type of file operation '" + args.operation + "'! Expect [link|copy]")
        exit(error_codes["OPTION_ERROR"])


#####################################################################
# Generate symbolic links between two files
#####################################################################
def generate_file_symbolic_link(src_file, des_file):
    src_file_abspath = os.getcwd() + "/" + src_file
    des_file_abspath = os.getcwd() + "/" + des_file
    # Create directorys for des_file if not exist
    des_dir = os.path.dirname(des_file_abspath)
    os.makedirs(des_dir, exist_ok=True)
    # Find relative path
    src_dir = os.path.dirname(src_file_abspath)
    src_file_relpath = os.path.relpath(src_dir, des_dir) + "/" + os.path.basename(src_file_abspath)
    # create space string for logging
    logging_space_src_file = " " * (max_filename_len - len(src_file))
    logging_space_des_file = " " * (max_filename_len - len(des_file))
    # If there is already a link, remove and create
    cand_files = os.scandir(des_dir)
    for entry in cand_files:
        if entry.is_symlink() and os.path.basename(entry.path) == os.path.basename(des_file):
            logging.warning(
                "Remove existing symbolic link: " + logging_space_des_file + str(entry.path)
            )
            os.unlink(entry.path)

    curr_dir = os.getcwd()
    os.chdir(des_dir)
    os.symlink(src_file_relpath, os.path.basename(des_file_abspath))
    os.chdir(curr_dir)
    logging.info(
        "Created file links "
        + logging_space_src_file
        + str(src_file)
        + " ----> "
        + logging_space_des_file
        + str(des_file)
    )


#####################################################################
# Generate symbolic links between two directories
#####################################################################
def generate_dir_symbolic_link(src_dir, des_dir):
    src_dir_abspath = os.getcwd() + "/" + src_dir
    des_dir_abspath = os.getcwd() + "/" + des_dir
    # Create directorys for des_dir if not exist
    des_dir_parent = os.path.dirname(des_dir_abspath)
    os.makedirs(des_dir_parent, exist_ok=True)
    # Find relative path
    src_dir_relpath = os.path.relpath(src_dir_abspath, des_dir_parent)
    # create space string for logging
    logging_space_src_dir = " " * (max_filename_len - len(src_dir))
    logging_space_des_dir = " " * (max_filename_len - len(des_dir))
    # If there is already a link, remove and create
    cand_files = os.scandir(des_dir_parent)
    for entry in cand_files:
        if entry.is_symlink() and os.path.basename(entry.path) == os.path.basename(des_dir):
            logging.warning(
                "Remove existing symbolic link: " + logging_space_des_dir + str(des_dir)
            )
            os.unlink(des_dir)

    curr_dir = os.getcwd()
    os.chdir(des_dir_parent)
    os.symlink(src_dir_relpath, os.path.basename(des_dir_abspath))
    os.chdir(curr_dir)
    logging.info(
        "Created directory links "
        + logging_space_src_dir
        + str(src_dir_relpath)
        + " ----> "
        + logging_space_des_dir
        + str(des_dir_abspath)
    )


#####################################################################
# Generate symbolic links based on a list of source and destination files
#####################################################################
def generate_symbolic_links(task_db):
    for src_file in task_db.keys():
        # A source file may have multiple destination file to be linked
        for des_file in task_db[src_file]:
            # Check if the link is between files or directories
            if os.path.isfile(src_file):
                generate_file_symbolic_link(src_file, des_file)

            if os.path.isdir(src_file):
                generate_dir_symbolic_link(src_file, des_file)


#####################################################################
# Create copies on a list of source and destination files
#####################################################################
def generate_copies(task_db):
    for src_file in task_db.keys():
        des_file = task_db[src_file]
        src_file_abspath = os.getcwd() + "/" + src_file
        des_file_abspath = os.getcwd() + "/" + des_file
        # Create directorys for des_file if not exist
        des_dir = os.path.dirname(des_file_abspath)
        os.makedirs(des_dir, exist_ok=True)
        # Find relative path
        src_dir = os.path.dirname(src_file_abspath)
        src_file_relpath = (
            os.path.relpath(src_dir, des_dir) + "/" + os.path.basename(src_file_abspath)
        )
        # create space string for logging
        logging_space_src_file = " " * (max_filename_len - len(src_file))
        logging_space_des_file = " " * (max_filename_len - len(des_file))
        # If there is already a file, remove and create
        if os.path.isfile(des_file_abspath):
            logging.warning("Remove existing file: " + logging_space_des_file + str(des_file))
            os.unlink(des_file_abspath)

        try:
            shutil.copy(src_file_abspath, des_file_abspath)
            logging.info(
                "Copied "
                + logging_space_src_file
                + str(src_file)
                + " ----> "
                + logging_space_des_file
                + str(des_file)
            )

        # If source and destination are same
        except shutil.SameFileError:
            logging.info(
                "Copying "
                + logging_space_src_file
                + str(src_file)
                + " ----> "
                + logging_space_des_file
                + str(des_file)
            )
            logging.error("Source and destination represents the same file.")
            exit(error_codes["ERROR"])

        # If there is any permission issue
        except PermissionError:
            logging.info(
                "Copying "
                + logging_space_src_file
                + str(src_file)
                + " ----> "
                + logging_space_des_file
                + str(des_file)
            )
            logging.error("Permission denied.")
            exit(error_codes["ERROR"])


#####################################################################
# Read task list from a yaml file
#####################################################################
def read_yaml_to_task_database(yaml_filename):
    task_db = {}
    with open(yaml_filename, "r") as stream:
        try:
            task_db = yaml.load(stream, Loader=yaml.FullLoader)
            logging.info("Found " + str(len(task_db)) + " tasks to create symbolic links")
        except yaml.YAMLError as exc:
            logging.error(exc)
            exit(error_codes["FILE_ERROR"])

    return task_db


#####################################################################
# Write result database to a yaml file
#####################################################################
def write_result_database_to_yaml(result_db, yaml_filename):
    with open(yaml_filename, "w") as yaml_file:
        yaml.dump(result_db, yaml_file, default_flow_style=False)


#####################################################################
# Main function
#####################################################################
if __name__ == "__main__":
    # Execute when the module is not initialized from an import statement

    # Parse the options and apply sanity checks
    parser = argparse.ArgumentParser(
        description="Create symbolic links with a given configuration file"
    )
    parser.add_argument("--config_file", required=True, help="Configuration file in YAML format")
    parser.add_argument(
        "--operation",
        default="link",
        help="File operation to perform. [link|copy] which create links or create a hard copy",
    )
    args = parser.parse_args()
    check_options(args)

    # Create a database for tasks
    task_db = {}
    task_db = read_yaml_to_task_database(args.config_file)

    # Generate links based on the task list in database
    if args.operation == "link":
        generate_symbolic_links(task_db)
        logging.info("Created " + str(len(task_db)) + " symbolic links")
        exit(error_codes["SUCCESS"])

    # Create copies based on the task list in database
    if args.operation == "copy":
        generate_copies(task_db)
        logging.info("Copied " + str(len(task_db)) + " files")
