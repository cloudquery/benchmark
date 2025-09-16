# CloudQuery Benchmark

This is a benchmark for CloudQuery. It is used to measure the performance of CloudQuery.

## Prerequisites

- Python version equal or higher than 3.11
- CloudQuery CLI installed (see [CloudQuery CLI](https://docs.cloudquery.io/docs))

## Setup

The benchmark will use only the configured sources, and optionally the S3 destination.

### AWS Source

Set an `AWS_LOCAL_PROFILE` environment variable to the AWS local profile you want to use for the benchmark.

For example, if your AWS credentials files looks like this:

```toml
[default]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY

[benchmark]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY
```

Then you can set the `AWS_LOCAL_PROFILE` environment variable to `benchmark` to use the `benchmark` profile, via:

```bash
export AWS_LOCAL_PROFILE=benchmark
```

Alternatively, you can set the `AWS_LOCAL_PROFILE` environment variable in the `bench_configs/source_aws.yml` file.

### Azure Source

1. Follow the instructions in [Azure Source](https://hub.cloudquery.io/plugins/source/cloudquery/azure/latest/docs#overview-authentication-with-environment-variables) to authenticate with Azure using environment variables.
2. Set an `AZURE_SUBSCRIPTION_ID` environment variable to the Azure subscription ID you want to use for the benchmark, for example:

```bash
export AZURE_SUBSCRIPTION_ID=YOUR_AZURE_SUBSCRIPTION_ID
```

### GCP Source

1. Ensure you have the Google Cloud CLI installed and run `gcloud auth application-default login` to set up Application Default Credentials.
2. Set an `GCP_PROJECT_ID` environment variable to the GCP project ID you want to use for the benchmark, for example:

```bash
export GCP_PROJECT_ID=YOUR_GCP_PROJECT_ID
```

### S3 Destination

To enable sending data to S3, set the following environment variables:

```bash
export S3_BUCKET_NAME=YOUR_S3_BUCKET_NAME
export S3_REGION=YOUR_S3_REGION
export S3_LOCAL_PROFILE=YOUR_S3_LOCAL_PROFILE
```

## Running the benchmark

```bash
pip install -r requirements.txt
python benchmark.py
```

### Advanced configuration

To generate enough resources to sync, we use the `CQ_DEBUG_SYNC_MULTIPLIER` to simulate more API calls to AWS, GCP and Azure.
You can update the code to generate more or less resources if you'd like.
