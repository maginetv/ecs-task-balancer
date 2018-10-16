# ECS  Tasks Rebalancer
This program is a lazy best effort tasks rebalancer in ECS intended to run periodically as a lambda function. It's job is to lazily rebalance ecs tasks across a cluster in a best effort mechansim.


## How it works

The rebalancing works by computing the standard deviation of running tasks disbursed onto the cluster. If the standard deviation is too high which results in a high coefficient of variance (COV) then the rebalancing procedure is invoked otherwise it's skipped. A good acceptable COV is defaulted between 0% and 25%, but this also can vary depending on the number of instances in the cluster and therefore needs adjustment accordingly.

For example consider the following distribution:

    `[13, 12, 4]`

which are number of tasks across 3 container instances. The standard deviation is a bit too high for this which computes to `4.93288286232` resulting in a high COV of 51% and has a mean value of `9.66666666667` tasks per cluster. This would require rebalancing.

On the other hand, a distribution of:

    `[16, 14, 14]`

is fairly good enough. The standard deviation is `1.15470053838` with a COV of `7.87295821622` and has a mean value of `14.6666666667` which is pretty good. This would not require rebalancing and would be skipped. Using just the mean or standard deviation is not good enough whereas the COV can give more accurate results b/w each dataset in the interation. The rebalancing has the following tweaking parameters to do a more accurate rebalancing which are:

`DRAIN_SLEEP_TIME`: This is the sleep time after every drainage of a container instance. A lower value could potentially create many invocation calls to the ECS API and would result in throttling. Acceptable values are b/w 10 and 30 seconds.

`DRAIN_TIMEOUT`: This is the draining timeout after which we stop drainage on the instance and activate it again. A higher value could potentially remove all tasks from the instance. Acceptable values are b/w 0 and 60 seconds.

`DRAIN_MAX_INSTANCES`: This is the maximum number of instances to drain during one instance of a rebalancing invocation. Acceptable values are b/w 0 and 3.

`REBALANCE_MAX_RETRY`: This is the maximum number of retries b/w successive drainage to see if rebalancing was successfully achieved. A higher value would try rebalancing over and over again which would lead to more drainage on container instances. Acceptable values are b/w 0 and 5.

`COV_PERCENT:` The acceptable coefficient of variation percent above which rebalancing would be triggered.

Note: Because it's a best effort rebalancing algorithm, it is intended to be run multiple time until it gets it right preferably via a cron job.

Read more [here](https://people.richland.edu/james/ictcm/2001/descriptive/helpvariance.html)


## How to run

To run the program locally, run the following command:

```bash
export AWS_REGION=eu-west-1
export DRAIN_TIMEOUT=45
export DRAIN_SLEEP_TIME=30
export DRAIN_MAX_INSTANCES=3
export REBALANCE_MAX_RETRY=3
export COV_PERCENT=25
python ecs_taskbalancer.py
```

The following IAM permissions are required for this to work:

```yaml
    Statement:
    - Effect: Allow
      Action:
        - 'logs:CreateLogGroup'
        - 'logs:CreateLogStream'
        - 'logs:PutLogEvents'
      Resource: !Sub 'arn:aws:logs:${AWS::Region}:*:*'
    - Effect: Allow
      Action:
        - ecs:DescribeContainerInstances
        - ecs:ListContainerInstances
        - ecs:DescribeContainerInstances
        - ecs:UpdateContainerInstancesState
      Resource: !Sub 'arn:aws:ecs:${AWS::Region}:${AWS::AccountId}:*/*'
    - Effect: Allow
      Action:
        - ecs:ListClusters
      Resource: '*'

```

## Testing


```bash

rake test

```

## Build


```bash

rake build

```

This will create a `build.zip` file in the `build/` folder which you can then upload to s3 or Lambda.


## Author
<a name="author"/>

Jude D'Souza (dsouza_jude@hotmail.com, jude.dsouza@magine.com)
