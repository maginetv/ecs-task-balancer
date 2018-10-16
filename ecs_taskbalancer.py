import os
import sys
import math
import time
import json
import logging
from datetime import datetime

import aws


# Setup logging
log = logging.getLogger()
for h in log.handlers:
    log.removeHandler(h)

log_format = '%(asctime)s %(levelname)s %(message)s'
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter(log_format))
log.addHandler(handler)
log.setLevel(logging.INFO)


# Default sleep time in seconds b/w draining
DRAIN_SLEEP_TIME = 30

# Default drain timeout time after which we stop the draining
DRAIN_TIMEOUT = 45

# Default max drainable instances
DRAIN_MAX_INSTANCES = 2

# Default max number of times to retry to rebalance after every drainage
REBALANCE_MAX_RETRY = 3

# Acceptable coefficient of variation
COV_PERCENT = 25


def compute_mean(arr):
    """ Compute mean """
    n = len(arr)
    summ = float(sum(arr)) / float(n)
    return summ


def compute_standard_deviation(arr, mean):
    """ Compute deviation of data """
    n = float(len(arr))
    summ = 0
    for i in arr:
        diff = (float(i) - float(mean))
        summ += pow(diff, 2)
    return math.sqrt(summ / (n-1))


def compute_coefficient_of_variation(mean, standard_deviation):
    return (float(standard_deviation) / float(mean)) * 100


def get_stats(values):
    mean = compute_mean(values)
    sd = compute_standard_deviation(values, mean)
    cov = compute_coefficient_of_variation(mean, sd)
    return mean, sd, cov


def get_num_task_distribution(region, cluster):
    """ Gets task distribution over container instances sorted by most tasks.

    Returns: sortedlist[
        {
            "instance_id": "...",
            "container_instance_arn": "...",
            "num_tasks": 133
        }
    ]
    """
    dist = []
    container_instances = aws.get_container_instances(
        region, cluster_name=cluster, status=aws.STATUS_ACTIVE
    )
    # Loop through all container instances in the cluster
    # Get container instance ARN and running tasks + pending tasks
    for i in container_instances:
        instance_id = i["ec2InstanceId"]
        container_instance_arn = i["containerInstanceArn"]
        num_tasks = i["runningTasksCount"] + i["pendingTasksCount"]
        dist.append(
            {
                "instance_id": instance_id,
                "container_instance_arn": container_instance_arn,
                "num_tasks": num_tasks
            }
        )

    # Sort by most task count
    sorted_dist = sorted(dist, key=lambda k: k["num_tasks"], reverse=True)
    return sorted_dist


def drain_instance(region, cluster, mean, num_tasks,
                   instance_arn, sleep_time, drain_timeout):
    """ Drain container instance of tasks until the instance
    has number of running tasks less or equal to the mean or
    until the drain timeout has reached.
    """

    # Drain container instance
    aws.update_container_instance_draining(
        region, cluster, instance_arn, status=aws.STATUS_DRAINING
    )
    log.info(
        "Draining instance={} with num_tasks={} until mean={}".format(
            instance_arn, num_tasks, mean
        )
    )

    # Drain until num tasks of the container reaches the mean tasks
    # to run on the container or we reach the drain timeout.
    time_start = datetime.now()
    while num_tasks > mean:
        time_elapsed = (datetime.now() - time_start).seconds
        time_remaining = drain_timeout - time_elapsed

        # Don't sleep more than the drain timeout
        if sleep_time > time_remaining:
            sleep_time = time_remaining + 3

        # Break on drain timeout
        if time_elapsed > drain_timeout:
            log.info(
                "Reached drain timeout={}, stopping drainage.".format(
                    drain_timeout
                )
            )
            break

        log.info("Sleeping for {}s ...".format(sleep_time))
        time.sleep(sleep_time)

        # Get updated state of container running tasks
        instance = aws.get_container_instances(
            region,
            cluster,
            container_instance_arn=instance_arn,
            status=aws.STATUS_DRAINING
        )[0]
        num_tasks = instance["runningTasksCount"]

    # Stop the draining
    log.info("Stopping draining of {}".format(instance_arn))
    resp = aws.update_container_instance_draining(
        region, cluster, instance_arn, status=aws.STATUS_ACTIVE
    )
    log.info("Draining stopped of {} with {} tasks left".format(
        instance_arn, resp["runningTasksCount"])
    )


def try_rebalancing_cluster(region, cluster, sleep_time, drain_timeout,
                            drain_max_instances, max_retries, cov_percent):
    """ Try to rebalance tasks across container instances of the cluster
    in a lazy but best effort fashion by offloading tasks from the instance
    onto other instances via container instance draining.

    Drain only until `drain_max_instances` or `max_retries`.
    """

    # Keep track of number of instances drained
    # This should not exceed `drain_max_instances`
    instance_count = 0

    # Keep track how many times we're draining to rebalance the cluster
    # This should not exceed max_retries.
    retry_count = 0

    while True:

        # Get task distribution over instance for this cluster
        dist = get_num_task_distribution(region, cluster)
        dist_values = [d["num_tasks"] for d in dist]
        if len(dist_values) == 0:
            log.info("No task distribution available")
            return

        if sum(dist_values) <= 1:
            log.info("Only 0 or 1 task is running! Rebalancing not required")
            return

        # Keep recomputing mean and SD after every drainage
        mean, sd, cov = get_stats(dist_values)
        log.info(
            "{} Task dist for {}, mean={}, sd={}, cov={}".format(
                cluster, dist_values, mean, sd, cov
            )
        )

        # Determine if rebalancing is needed
        if cov <= cov_percent:
            log.info("Coef.Of.variation looks good for {}!".format(cluster))
            return

        # Try rebalancing, i.e. pick the first instance with most tasks
        log.info("Too high COV in {}. Rebalancing!".format(cluster))

        # Sorted by most tasks, pick the first one
        instance_arn = dist[0]["container_instance_arn"]
        num_tasks = dist[0]["num_tasks"]
        drain_instance(region, cluster, mean, num_tasks,
                       instance_arn, sleep_time, drain_timeout)

        # Check if we have exceeded max draining instances
        instance_count += 1
        if instance_count >= drain_max_instances:
            log.info(
                "Exceeded max draining instances, instance_count={}".format(
                    instance_count
                )
            )
            return

        # Check if we have exceeded max rebalance retries
        retry_count += 1
        if retry_count >= max_retries:
            log.info(
                "Exceeded max rebalance retries. retry_count={}".format(
                    retry_count
                )
            )

        # Reduce drain timeout on every iteration
        drain_timeout = drain_timeout / 2.00
        log.info("Reducing drain_timeout={}".format(drain_timeout))

        # Sleep after draining and recompute SD for further rebalancing needed
        # It takes a while for the number of tasks to be recomputed.
        log.info("Sleeping for a bit b/w drainage ...")
        time.sleep(60)


def main(event, context):
    """ Entry point to lambda function. This lambda lazily rebalance tasks
    across the cluster by draining container instances with the most tasks.
    """
    log.info("Starting program ...")
    log.info("Event={}".format(json.dumps(event)))

    # Get rebalancer settings
    region = os.environ["AWS_REGION"]
    sleep_time = int(os.environ.get("DRAIN_SLEEP_TIME", DRAIN_SLEEP_TIME))
    drain_timeout = int(os.environ.get("DRAIN_TIMEOUT", DRAIN_TIMEOUT))
    drain_max_instances = int(
        os.environ.get("DRAIN_MAX_INSTANCES", DRAIN_MAX_INSTANCES)
    )
    max_retries = int(
        os.environ.get("REBALANCE_MAX_RETRY", REBALANCE_MAX_RETRY)
    )
    cov_percent = float(
        os.environ.get("COV_PERCENT", COV_PERCENT)
    )
    log.info(
        """Settings, sleep_time={}, drain_timeout={}, max_instances={},
        max_retries={}, cov_percent={}
        """.format(
            sleep_time, drain_timeout,
            drain_max_instances, max_retries, cov_percent
        )
    )

    # Adjust to avoid rate limiting errors or too long sleep / drain time
    sleep_time = min(30, sleep_time)
    sleep_time = max(10, sleep_time)
    drain_timeout = min(60, drain_timeout)
    drain_max_instances = min(3, drain_max_instances)
    max_retries = min(5, max_retries)
    cov_percent = min(30, cov_percent)
    log.info("""Adjusted sleep_time={} drain_timeout={}
             max_instances={}, max_retries={}, cov_percent={}
             """.format(
        sleep_time, drain_timeout,
        drain_max_instances, max_retries, cov_percent
    ))

    # Get all clusters
    cluster_names = aws.list_clusters(region)
    log.info("Clusters {} Found".format(cluster_names))

    # Try rebalancing one cluster at a time
    for cluster in cluster_names:
        try_rebalancing_cluster(region, cluster, sleep_time, drain_timeout,
                                drain_max_instances, max_retries, cov_percent)


if __name__ == '__main__':
    main({}, None)
