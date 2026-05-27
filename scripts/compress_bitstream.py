#####################################################################
# A script with multiple objectives
# - Compress all the bitstream files in this directory (in a recursive way). Results will be saved in a yaml file
# - Uncompress for all the bitstream files in this directory (in a recursive way). File list comes from a yaml file
#####################################################################
import os
from os.path import dirname, abspath
import argparse
import logging
import subprocess
import tarfile
import yaml
import re
import time
from datetime import timedelta
import datetime
import threading
import filecmp
import gzip
import shutil

#####################################################################
# Error codes
#####################################################################
error_codes = {"SUCCESS": 0, "COMPRESS_ERROR": 1, "OPTION_ERROR": 2, "FILE_ERROR": 3}

space_limit = 80  # Maximum space tuned for the screen width

#####################################################################
# Initialize logger
#####################################################################
logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

#####################################################################
# Check options
# - Only one of 'create_md5' and 'check_md5' is enabled
#####################################################################
def check_options(args):
    if args.compress and args.uncompress:
        logging.error("Only one of options 'compress' and 'uncompress' can be enabled!")
        exit(error_codes["SUCCESS"])

    if (not args.compress) and (not args.uncompress):
        logging.error("Must enable one of options 'compress' and 'uncompress'!")
        exit(error_codes["SUCCESS"])


#####################################################################
# Compress a specific bitstream file
#####################################################################
def compress_bitstream_file(
    bitstream_filename, compressed_filename, compression_type, tarfile_format
):
    try:
        fformat = f"tarfile.{tarfile_format}"
        logging.info(f"Use tar file format: {tarfile_format}")
        with tarfile.open(
            compressed_filename, "w:" + compression_type, format=eval(fformat)
        ) as tar:
            tar.add(bitstream_filename)
    except:
        logging.error("Error when compressing file: " + str(compressed_filename))
        return 1

    return 0


#####################################################################
# Compress a specific bitstream file using gzip
#####################################################################
def gzip_bitstream_file(bitstream_filename, compressed_filename):
    try:
        logging.info(f"Now use gzip to compress file: {compressed_filename}")
        with open(bitstream_filename, "rb") as f_in:
            with gzip.open(compressed_filename, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
    except:
        logging.error("Error when gzip compressing file: " + str(compressed_filename))
        return 1

    return 0


#####################################################################
# Compress a specific bitstream file using a thread
#####################################################################
def thread_compress_bitstream_file(
    thread_sema,
    bitstream_filename,
    compressed_filename,
    compression_type,
    tarfile_format,
    gzip_only,
    job_status,
    job_time,
    skip_same_file,
):
    with thread_sema:
        thread_name = threading.current_thread().name

        job_name = bitstream_filename

        # Log runtime
        start_time = time.time()
        logging.debug("Input file: " + job_name)

        start_time_str = datetime.datetime.fromtimestamp(start_time).isoformat()
        time_logging_space = (
            "." * (space_limit - len(job_name) - len(" start at") - len(start_time_str) - 2) + " "
        )
        logging.info(job_name + " start at" + time_logging_space + start_time_str)

        # Compare file content: if they are same, we skip compression
        do_compression = True
        if skip_same_file:
            # If there is an existing compressed copy, uncompress it and compare file content
            # If there is no change in file content, skip compressing the copy
            if os.path.exists(compressed_filename):
                # Rename current file to a back-up file name
                bitstream_filename_bak = bitstream_filename + ".bak"
                os.rename(bitstream_filename, bitstream_filename_bak)
                # Uncompress to the same copy
                if gzip_only:
                    gzip_uncompress_bitstream_file(compressed_filename)
                else:
                    uncompress_bitstream_file(compressed_filename, compression_type, tarfile_format)
                # Diff the content
                if filecmp.cmp(bitstream_filename_bak, bitstream_filename):
                    logging.info(
                        "Skip '"
                        + bitstream_filename
                        + "' due to content unchanged when compared to an existing compressed copy '"
                        + bitstream_filename_bak
                        + "'"
                    )
                    job_status[job_name] = 0
                    do_compression = False
                # Recover renamed files
                os.rename(bitstream_filename_bak, bitstream_filename)

        if do_compression:
            if gzip_only:
                job_status[job_name] = gzip_bitstream_file(bitstream_filename, compressed_filename)
            else:
                job_status[job_name] = compress_bitstream_file(
                    bitstream_filename, compressed_filename, compression_type, tarfile_format
                )

        end_time = time.time()
        job_time[job_name] = timedelta(seconds=(end_time - start_time))

        end_time_str = datetime.datetime.fromtimestamp(end_time).isoformat()
        logging.info(job_name + " ends  at" + time_logging_space + end_time_str)

        return job_status


#####################################################################
# UnCompress a specific bitstream file
#####################################################################
def uncompress_bitstream_file(compressed_filename, compression_type, tarfile_format):
    try:
        if not tarfile.is_tarfile(compressed_filename):
            logging.error(compressed_filename + " is not a tar file")
            exit(error_codes["COMPRESS_ERROR"])
        fformat = f"tarfile.{tarfile_format}"
        logging.info(f"Use tar file format: {tarfile_format}")
        with tarfile.open(
            compressed_filename, "r:" + compression_type, format=eval(fformat)
        ) as tar:
            tar.extractall()
    except:
        logger.error("Error when uncompressing file: " + str(compressed_filename))
        return 1

    return 0


#####################################################################
# Compress a specific bitstream file using gzip
#####################################################################
def gzip_uncompress_bitstream_file(compressed_filename):
    try:
        bitstream_filename = os.path.splitext(compressed_filename)[0]
        with gzip.open(compressed_filename, "rb") as f_in:
            with open(bitstream_filename, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
    except:
        logging.error("Error when gzip uncompressing file: " + str(compressed_filename))
        return 1

    return 0


#####################################################################
# Uncompress a specific bitstream file using a thread
#####################################################################
def thread_uncompress_bitstream_file(
    thread_sema,
    compressed_filename,
    compression_type,
    tarfile_format,
    gzip_only,
    job_status,
    job_time,
):
    with thread_sema:
        thread_name = threading.current_thread().name

        job_name = compressed_filename
        # Log runtime
        start_time = time.time()
        logging.debug("Input file: " + job_name)

        start_time_str = datetime.datetime.fromtimestamp(start_time).isoformat()
        time_logging_space = (
            "." * (space_limit - len(job_name) - len(" start at") - len(start_time_str) - 2) + " "
        )
        logging.info(job_name + " start at" + time_logging_space + start_time_str)

        if gzip_only:
            job_status[job_name] = gzip_uncompress_bitstream_file(compressed_filename)
        else:
            job_status[job_name] = uncompress_bitstream_file(
                compressed_filename, compression_type, tarfile_format
            )
        end_time = time.time()
        job_time[job_name] = timedelta(seconds=(end_time - start_time))

        end_time_str = datetime.datetime.fromtimestamp(end_time).isoformat()
        logging.info(job_name + " ends at" + time_logging_space + end_time_str)

        return job_status


#####################################################################
# Find all the bitstream files under a given directory
# and compress each of them
#####################################################################
def glob_and_compress_bitstream_files(
    file_db,
    root_dir,
    bitstream_file_postfix,
    compressed_file_postfix,
    tarfile_format,
    gzip_only,
    max_num_jobs,
    new_thread_wait_time,
    skip_same_file,
):
    num_failures = 0

    # Create thread pool
    thread_sema = threading.BoundedSemaphore(value=max_num_jobs)
    thread_list = []

    # Job status dashboard
    job_status = {}
    job_time = {}

    for src_file_postfix in bitstream_file_postfix.split(","):
        for root, dirs, files in os.walk(root_dir):
            for src_file in files:
                # Only focus on bitstream files
                if not src_file.endswith(src_file_postfix):
                    continue

                # Get relative path to the file. This is important to keep tracking the location of files
                rel_dir = os.path.relpath(root, root_dir)
                rel_src_file = os.path.join(rel_dir, src_file)
                rel_des_file = rel_src_file + "." + compressed_file_postfix
                file_db[rel_src_file] = rel_des_file
                # Compress
                cur_thread = threading.Thread(
                    target=thread_compress_bitstream_file,
                    args=(
                        thread_sema,
                        rel_src_file,
                        rel_des_file,
                        compressed_file_postfix,
                        tarfile_format,
                        gzip_only,
                        job_status,
                        job_time,
                        skip_same_file,
                    ),
                )
                cur_thread.start()
                thread_list.append(cur_thread)
                time.sleep(
                    new_thread_wait_time
                )  # Give a wait time before starting the next thread. Avoid any conflicts in switching directories

    for cur_thread in thread_list:
        cur_thread.join()

    for key in file_db.keys():
        curr_job_status = job_status[key]
        # Create a space when logging
        logging_space = " " + "." * (space_limit - len(key) - 2) + " "
        num_failures = num_failures + curr_job_status
        if curr_job_status == 0:
            logging.info(key + logging_space + "[Pass]")
        else:
            logging.info(key + logging_space + "[Fail]")
        # Show runtime
        time_diff = job_time[key]
        time_str = "took " + str(time_diff)
        time_logging_space = "." * (space_limit - len(key) - len(time_str) - 2) + " "
        logging.info(key + time_logging_space + time_str)

    return num_failures


#####################################################################
# Find all the bitstream files in the database
# and uncompress each of them
#####################################################################
def uncompress_bitstream_files(
    file_db, compression_type, tarfile_format, gzip_only, max_num_jobs, new_thread_wait_time
):
    num_failures = 0

    # Create thread pool
    thread_sema = threading.BoundedSemaphore(value=max_num_jobs)
    thread_list = []

    # Job status dashboard
    job_status = {}
    job_time = {}

    for bitfile in file_db.keys():
        # Find bitfile dirpath
        des_dir = os.path.dirname(file_db[bitfile])
        cur_thread = threading.Thread(
            target=thread_uncompress_bitstream_file,
            args=(
                thread_sema,
                file_db[bitfile],
                compression_type,
                tarfile_format,
                gzip_only,
                job_status,
                job_time,
            ),
        )
        cur_thread.start()
        thread_list.append(cur_thread)
        time.sleep(
            new_thread_wait_time
        )  # Give a wait time before starting the next thread. Avoid any conflicts in switching directories

    for cur_thread in thread_list:
        cur_thread.join()

    for key in file_db.keys():
        curr_job_status = job_status[file_db[key]]
        # Create a space when logging
        logging_space = " " + "." * (space_limit - len(key) - 2) + " "
        num_failures = num_failures + curr_job_status
        if curr_job_status == 0:
            logging.info(file_db[key] + logging_space + "[Pass]")
        else:
            logging.info(file_db[key] + logging_space + "[Fail]")
        # Show runtime
        time_diff = job_time[file_db[key]]
        time_str = "took " + str(time_diff)
        time_logging_space = "." * (space_limit - len(file_db[key]) - len(time_str) - 2) + " "
        logging.info(file_db[key] + time_logging_space + time_str)

    return num_failures


#####################################################################
# Read file database to a yaml file
#####################################################################
def read_yaml_to_file_db(yaml_filename):
    file_db = {}
    with open(yaml_filename, "r") as stream:
        try:
            file_db = yaml.load(stream, Loader=yaml.FullLoader)
            logging.info("Found " + str(len(file_db)) + " files to compress/uncompress")
        except yaml.YAMLError as exc:
            logging.error(exc)
            exit(error_codes["FILE_ERROR"])

    return file_db


#####################################################################
# Write file database to a yaml file
#####################################################################
def write_file_db_to_yaml(file_db, yaml_filename):
    with open(yaml_filename, "w") as yaml_file:
        yaml.dump(file_db, yaml_file, default_flow_style=False)


#####################################################################
# Main function
#####################################################################
if __name__ == "__main__":
    # Execute when the module is not initialized from an import statement

    # Parse the options and apply sanity checks
    parser = argparse.ArgumentParser(description="Compress/Uncompress bitstream files")
    parser.add_argument("--compress", action="store_true", help="Compress bitstream files")
    parser.add_argument(
        "--uncompress", action="store_true", help="Uncompress bitstream files with a given list"
    )
    parser.add_argument(
        "--file_list",
        required=True,
        help="A file contains a list of bitstream files and compressed file names; For compress mode, it is an output file; For uncompress mode, it is an input file",
    )
    parser.add_argument(
        "--root_dir",
        default="./",
        help="Define the directory which contains bitstream files. This script will search all the files under it",
    )
    parser.add_argument(
        "--bitstream_file_postfix",
        default=".xml",
        help="Define the postfix of bitstream files. It will be used when globbing files under root directory. Use ',' to split if there should be multiple postfix to be considered",
    )
    parser.add_argument(
        "--compressed_file_postfix",
        default="gz",
        help="Define the postfix of compressed files. It will be used when compressing files under root directory",
    )
    parser.add_argument(
        "--tarfile_format",
        default="PAX_FORMAT",
        type=str,
        choices=["GNU_FORMAT", "PAX_FORMAT"],
        help="Define the format for created tar file. By default, use POSIX.1-2001 (PAX)",
    )
    parser.add_argument(
        "--gzip_only",
        action="store_true",
        help="Only use gzip during compression. Tar is not considered",
    )
    parser.add_argument(
        "--new_thread_wait_time",
        type=float,
        default=0.1,
        help="Specify the waiting time before starting a new thread (unit: second)",
    )
    parser.add_argument(
        "--j", type=int, default=2, help="Specify maximum number of jobs to be run in parallel"
    )
    parser.add_argument(
        "--skip_same_file",
        action="store_true",
        help="Skip compressing for the file whose content is not changed. Only applicable to file compression",
    )
    args = parser.parse_args()
    check_options(args)

    # Create an empty database
    file_db = {}

    # Compress bitstream files if enabled
    if args.compress:
        # Currently only support local directory
        logging.info("Will consider bitstream file postfix: " + args.bitstream_file_postfix)
        num_errors = glob_and_compress_bitstream_files(
            file_db,
            args.root_dir,
            args.bitstream_file_postfix,
            args.compressed_file_postfix,
            args.tarfile_format,
            args.gzip_only,
            args.j,
            args.new_thread_wait_time,
            args.skip_same_file,
        )
        write_file_db_to_yaml(file_db, args.file_list)
        logging.info(
            "Compressed " + str(len(file_db)) + " files and outputted to '" + args.file_list + "'"
        )
        logging.info("\tPassed " + str(len(file_db) - num_errors))
        logging.info("\tFailed " + str(num_errors))

    # Uncompress bitstream files from a yaml file
    if args.uncompress:
        num_errors = 0
        file_db = read_yaml_to_file_db(args.file_list)
        num_errors = uncompress_bitstream_files(
            file_db,
            args.compressed_file_postfix,
            args.tarfile_format,
            args.gzip_only,
            args.j,
            args.new_thread_wait_time,
        )
        if num_errors == 0:
            logging.info("Uncompressed " + str(len(file_db)) + " files")
            exit(error_codes["SUCCESS"])
        else:
            logging.info("Uncompression failed in " + str(num_errors) + " cases!")
            exit(error_codes["COMPRESS_ERROR"])
