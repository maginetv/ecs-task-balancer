import boto3

STATUS_ACTIVE = "ACTIVE"
STATUS_DRAINING = "DRAINING"


def list_clusters(region):
    ecs = boto3.client("ecs", region)
    cluster_names = []
    paginator = ecs.get_paginator("list_clusters")
    pages = paginator.paginate()
    for page in pages:
        for cluster_arn in page["clusterArns"]:
            cluster_name = cluster_arn.split("/")[1]

            # This check is added due to some weird bug where the ECS
            # API shows the instance id in both default and the real cluster.
            # To workaround this bug, we skip draining on
            # the "default" cluster.
            if cluster_name == "default":
                continue
            cluster_names.append(cluster_name)

    return cluster_names


def get_container_instances(region,
                            cluster_name,
                            container_instance_arn=None,
                            status=STATUS_ACTIVE):
    ecs = boto3.client('ecs', region)
    container_instances = []

    if container_instance_arn:
        resp = ecs.describe_container_instances(
            cluster=cluster_name,
            containerInstances=[container_instance_arn]
        )
        container_instances = resp["containerInstances"]
    else:
        paginator = ecs.get_paginator("list_container_instances")
        pages = paginator.paginate(cluster=cluster_name, status=status)
        for page in pages:
            container_instance_arns = page["containerInstanceArns"]
            resp = ecs.describe_container_instances(
                cluster=cluster_name,
                containerInstances=container_instance_arns
            )
            container_instances.extend(resp["containerInstances"])
    return container_instances


def update_container_instance_draining(region,
                                       cluster_name,
                                       container_instance_arn,
                                       status):
    ecs = boto3.client('ecs', region)
    resp = ecs.update_container_instances_state(
        cluster=cluster_name,
        containerInstances=[container_instance_arn],
        status=status
    )
    return resp["containerInstances"][0]
