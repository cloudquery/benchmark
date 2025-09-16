#!/usr/bin/env python3
"""
CloudQuery Performance Benchmark
Official technical benchmark for measuring CloudQuery data synchronization performance.
"""

import sys
import os
import subprocess
import logging
from datetime import datetime, timedelta
import pandas as pd
import pyarrow as pa
import colorlog
import psutil
from pathlib import Path
from enum import Enum
import platform

benchmark_results_dir = "benchmark_results"


class ColumnNames(Enum):
    TOTAL_ROWS = "Total Rows"
    TOTAL_BYTES = "Total Bytes"
    DURATION = "Duration"
    AVERAGE_CPU = "Average CPU"
    MAX_MEMORY_MD = "Max Memory (MB)"


def setup_logging():
    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s%(levelname)s:%(reset)s %(message)s",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red,bg_white",
            },
        )
    )

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)


def get_cloud_syncs_to_run():
    sources = ["aws", "azure", "gcp"]
    destinations = ["s3", "file"]

    if not os.getenv("AWS_LOCAL_PROFILE"):
        logging.warning("AWS_LOCAL_PROFILE is not set, skipping AWS source")
        sources.remove("aws")
    if not (
        os.getenv("AZURE_SUBSCRIPTION_ID")
        and os.getenv("AZURE_TENANT_ID")
        and os.getenv("AZURE_CLIENT_ID")
        and os.getenv("AZURE_CLIENT_SECRET")
    ):
        logging.warning(
            "AZURE_SUBSCRIPTION_ID, AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET are not set, skipping Azure source"
        )
        sources.remove("azure")
    if not os.getenv("GCP_PROJECT_ID"):
        logging.warning("GCP_PROJECT_ID is not set, skipping GCP source")
        sources.remove("gcp")
    if not (
        os.getenv("S3_BUCKET_NAME")
        and os.getenv("S3_REGION")
        and os.getenv("S3_LOCAL_PROFILE")
    ):
        logging.warning(
            "S3_BUCKET_NAME, S3_REGION, and S3_LOCAL_PROFILE are not set, skipping S3 destination"
        )
        destinations.remove("s3")

    return sources, destinations


def read_parquet_files(results_dir, pattern):
    total_rows = 0
    total_bytes = 0
    files = Path(results_dir).glob(pattern + ".parquet")
    for file in files:
        logging.debug(f"Reading {file}")
        try:
            df = pd.read_parquet(file, engine="fastparquet")
            table = pa.Table.from_pandas(df)
            total_rows += table.num_rows
            total_bytes += table.nbytes
            logging.debug(
                f"Read {table.num_rows} rows and {table.nbytes / 1024} KB from {file}"
            )
        except Exception as e:
            logging.error(f"Error reading {file}: {e}")
            continue

    return total_rows, total_bytes


def get_gb_per_hour(total_bytes, sync_duration):
    return (total_bytes / 1024 / 1024 / 1024) / sync_duration.total_seconds() * 3600


def track_cpu_and_memory(process):
    p = psutil.Process(process.pid)
    all = {}
    cpu_count = psutil.cpu_count()
    try:
        while process.poll() is None:
            procs = [p] + p.children(recursive=True)
            for proc in procs:
                key = proc.pid
                if not all.get(key):
                    all[key] = {
                        "cpu_measurements": [],
                        "max_memory_mb": 0,
                    }
                all[key]["cpu_measurements"].append(
                    proc.cpu_percent(interval=1) / cpu_count
                )
                all[key]["max_memory_mb"] = max(
                    all[key]["max_memory_mb"], proc.memory_info().rss / (1024 * 1024)
                )
    except psutil.NoSuchProcess:
        pass

    for key, value in all.items():
        value["average_cpu"] = sum(value["cpu_measurements"]) / len(
            value["cpu_measurements"]
        )
        value["max_memory_mb"] = value["max_memory_mb"]

    average_cpu = sum(value["average_cpu"] for value in all.values())
    max_memory_mb = sum(value["max_memory_mb"] for value in all.values())

    return average_cpu, max_memory_mb


def run_sync(benchmark_output_dir, source, destinations, envs={}):
    logging.info(f"Running sync from {source} to {','.join(destinations)}")
    args = [
        "cloudquery",
        "sync",
        f"bench_configs/source_{source}.yml",
    ]
    for destination in destinations:
        args.append(f"bench_configs/dest_{destination}.yml")

    env = os.environ.copy()
    env["DESTINATIONS"] = f"[{','.join(destinations)}]"
    env["BENCHMARK_OUTPUT_DIR"] = benchmark_output_dir
    source_multiplier = {
        "aws": 40,
        "azure": 8,
        "gcp": 15,
        "file": 1,
    }
    # This generates 50 times more resources to sync
    env["CQ_DEBUG_SYNC_MULTIPLIER"] = str(source_multiplier[source])
    for key, value in envs.items():
        env[key] = value
    logging.info(f"Running sync with args: {args}")
    process = subprocess.Popen(args, env=env)
    return track_cpu_and_memory(process)


def print_benchmark_info(benchmarkResults):
    benchResultsPretty = {}
    for key, value in benchmarkResults.items():
        benchResultsPretty[key.upper()] = {
            "Total Rows": value[ColumnNames.TOTAL_ROWS.value],
            "Total MB": value[ColumnNames.TOTAL_BYTES.value] / 1024 / 1024,
            "Duration (s)": value[ColumnNames.DURATION.value].total_seconds(),
            "GB/Hour": get_gb_per_hour(
                value[ColumnNames.TOTAL_BYTES.value],
                value[ColumnNames.DURATION.value],
            ),
            "Average CPU": value[ColumnNames.AVERAGE_CPU.value],
            "Max Memory (MB)": value[ColumnNames.MAX_MEMORY_MD.value],
        }

    print(pd.DataFrame(benchResultsPretty).T)


def get_cpu_brand():
    try:
        model = (
            subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"], stderr=subprocess.STDOUT
            )
            .decode()
            .strip()
        )
        return model
    except Exception as e:
        return None


def print_machine_info():
    machine_info = {
        "Platform": [platform.platform()],
        "CPU Cores": [psutil.cpu_count()],
        "RAM GB": [psutil.virtual_memory().total / (1024 * 1024 * 1024)],
    }
    cpu_branch = get_cpu_brand()
    if cpu_branch:
        machine_info["CPU Brand"] = [cpu_branch]
    print(pd.DataFrame(machine_info).T)


def main():
    setup_logging()
    logging.info("Running benchmark...")
    start_time = datetime.now()
    benchmarkResults = {}
    try:
        benchmark_output_dir = (
            f"{benchmark_results_dir}/{start_time.strftime('%Y%m%d_%H%M%S')}"
        )
        # First run the cloud syncs
        sources, destinations = get_cloud_syncs_to_run()
        for source in sources:
            sync_time = datetime.now()
            average_cpu, max_memory_mb = run_sync(
                benchmark_output_dir, source, destinations
            )
            sync_duration = datetime.now() - sync_time
            total_rows, total_bytes = read_parquet_files(
                benchmark_output_dir, source + "_*"
            )
            benchmarkResults[source] = {
                ColumnNames.TOTAL_ROWS.value: total_rows,
                ColumnNames.TOTAL_BYTES.value: total_bytes,
                ColumnNames.DURATION.value: sync_duration,
                ColumnNames.AVERAGE_CPU.value: average_cpu,
                ColumnNames.MAX_MEMORY_MD.value: max_memory_mb,
            }

        # Then a synthetic sync from file to destinations to measure without any API limits
        if not os.path.exists(benchmark_output_dir):
            raise ValueError(
                f"benchmark_results directory does not exist, please set up any of the sources first"
            )

        logging.info(
            f"Running synthetic sync from file to destinations for {benchmark_output_dir}"
        )
        total_rows, total_bytes = read_parquet_files(benchmark_output_dir, "*")
        sync_time = datetime.now()
        average_cpu, max_memory_mb = run_sync(
            f"{benchmark_output_dir}/file",
            "file",
            destinations,
            {"BENCHMARK_RESULTS": benchmark_output_dir},
        )
        sync_duration = datetime.now() - sync_time
        benchmarkResults["file"] = {
            ColumnNames.TOTAL_ROWS.value: total_rows,
            ColumnNames.TOTAL_BYTES.value: total_bytes,
            ColumnNames.DURATION.value: sync_duration,
            ColumnNames.AVERAGE_CPU.value: average_cpu,
            ColumnNames.MAX_MEMORY_MD.value: max_memory_mb,
        }

    except Exception as e:
        logging.error(f"Error running benchmark: {e}")
        sys.exit(1)
    finally:
        print_benchmark_info(benchmarkResults)
        print_machine_info()


if __name__ == "__main__":
    main()
