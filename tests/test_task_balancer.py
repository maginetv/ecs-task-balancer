import os
from mock import patch, Mock, ANY, call
import nose.tools as nt

import aws
import ecs_taskbalancer


class TestTaskBalancer(object):


    def setup(self):
        self.region = "eu-west-1"
        self.cluster = "test"
        self.sleep_time = -1
        self.drain_timeout = -1
        self.drain_max_instances = 1
        self.max_retries = 1
        self.cov_percent = 1

    @patch('aws.update_container_instance_draining')
    @patch('aws.get_container_instances')
    @patch('aws.activate_instances_in_cluster')
    def test_cluster_is_rebalanced_when_distribution_is_uneven(self, activate_mock, get_instances_mock, drain_mock):
        test_dataset = [15, 1, 0]
        get_instances_mock.return_value = [
            {
                "ec2InstanceId": "i-aaaaa",
                "containerInstanceArn": "arn:aws:ecs:eu-west-1:000:container-instance/xxx",
                "runningTasksCount": test_dataset[0],
                "pendingTasksCount": 0
            },
            {
                "ec2InstanceId": "i-bbbbb",
                "containerInstanceArn": "arn:aws:ecs:eu-west-1:000:container-instance/yyy",
                "runningTasksCount": test_dataset[1],
                "pendingTasksCount": 0
            },
            {
                "ec2InstanceId": "i-ccccc",
                "containerInstanceArn": "arn:aws:ecs:eu-west-1:000:container-instance/zzz",
                "runningTasksCount": test_dataset[2],
                "pendingTasksCount": 0
            }
        ]
        ecs_taskbalancer.try_rebalancing_cluster(
            self.region, self.cluster, self.sleep_time, self.drain_timeout,
            self.drain_max_instances, self.max_retries, self.cov_percent
        )
        # Assert that the call was first made to drain the instance
        # and then to activate the instance back so that
        # rebalancing can occur.
        drain_mock.assert_has_calls(
            [
                call(self.region, self.cluster, ANY, status=aws.STATUS_DRAINING),
                call(self.region, self.cluster, ANY, status=aws.STATUS_ACTIVE)
            ]
        )

    @patch('aws.update_container_instance_draining')
    @patch('aws.get_container_instances')
    @patch('aws.activate_instances_in_cluster')
    def test_cluster_is_not_rebalanced_when_distribution_is_even(self, activate_mock, get_instances_mock, drain_mock):
        test_dataset = [15, 15, 15]
        get_instances_mock.return_value = [
            {
                "ec2InstanceId": "i-aaaaa",
                "containerInstanceArn": "arn:aws:ecs:eu-west-1:000:container-instance/xxx",
                "runningTasksCount": test_dataset[0],
                "pendingTasksCount": 0
            },
            {
                "ec2InstanceId": "i-bbbbb",
                "containerInstanceArn": "arn:aws:ecs:eu-west-1:000:container-instance/yyy",
                "runningTasksCount": test_dataset[1],
                "pendingTasksCount": 0
            },
            {
                "ec2InstanceId": "i-ccccc",
                "containerInstanceArn": "arn:aws:ecs:eu-west-1:000:container-instance/zzz",
                "runningTasksCount": test_dataset[2],
                "pendingTasksCount": 0
            }
        ]
        ecs_taskbalancer.try_rebalancing_cluster(
            self.region, self.cluster, self.sleep_time, self.drain_timeout,
            self.drain_max_instances, self.max_retries, self.cov_percent
        )

        # A call to get the distribution
        get_instances_mock.assert_called_once_with(self.region, cluster_name=self.cluster, status=aws.STATUS_ACTIVE)

        # Because the distribution is good, rebalancing should not occur
        drain_mock.assert_not_called()

    @patch('aws.update_container_instance_draining')
    @patch('aws.get_container_instances')
    @patch('aws.activate_instances_in_cluster')
    def test_cluster_is_not_rebalanced_for_zero_or_single_tasks(self, activate_mock, get_instances_mock, drain_mock):
        for test_dataset in [[0, 0, 0], [1, 0, 0]]:
            get_instances_mock.return_value = [
                {
                    "ec2InstanceId": "i-aaaaa",
                    "containerInstanceArn": "arn:aws:ecs:eu-west-1:000:container-instance/xxx",
                    "runningTasksCount": test_dataset[0],
                    "pendingTasksCount": 0
                },
                {
                    "ec2InstanceId": "i-bbbbb",
                    "containerInstanceArn": "arn:aws:ecs:eu-west-1:000:container-instance/yyy",
                    "runningTasksCount": test_dataset[1],
                    "pendingTasksCount": 0
                },
                {
                    "ec2InstanceId": "i-ccccc",
                    "containerInstanceArn": "arn:aws:ecs:eu-west-1:000:container-instance/zzz",
                    "runningTasksCount": test_dataset[2],
                    "pendingTasksCount": 0
                }
            ]
            ecs_taskbalancer.try_rebalancing_cluster(
                self.region, self.cluster, self.sleep_time, self.drain_timeout,
                self.drain_max_instances, self.max_retries, self.cov_percent
            )

        # A call to get the distribution
        get_instances_mock.assert_has_calls(
            [
                call(self.region, cluster_name=self.cluster, status=aws.STATUS_ACTIVE),
                call(self.region, cluster_name=self.cluster, status=aws.STATUS_ACTIVE)
            ]
        )

        # No rebalancing required, so no  calls to drain the instance
        drain_mock.assert_not_called()

    @patch('aws.update_container_instance_draining')
    @patch('aws.get_container_instances')
    @patch('aws.activate_instances_in_cluster')
    def test_cluster_does_not_rebalance_for_single_instance(self, activate_mock, get_instances_mock, drain_mock):
        task_count = 3
        get_instances_mock.return_value = [
            {
                "ec2InstanceId": "i-aaaaa",
                "containerInstanceArn": "arn:aws:ecs:eu-west-1:000:container-instance/xxx",
                "runningTasksCount": task_count,
                "pendingTasksCount": 0
            }
        ]
        ecs_taskbalancer.try_rebalancing_cluster(
            self.region, self.cluster, self.sleep_time, self.drain_timeout,
            self.drain_max_instances, self.max_retries, self.cov_percent
        )

        # No rebalancing required, so no  calls to drain the instance
        drain_mock.assert_not_called()
