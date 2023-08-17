from string import Template
import requests


# create policy; return policy ID
def create_policy(endpoint, headers, account_id, logger):
    logger.info('Creating 2W-CPU-Mem-100 alert policy...')
    policy_template = Template("""
    mutation PolicyCreate {
      alertsPolicyCreate(
        accountId: $account_id
        policy: {name: "2W-CPU-Mem-100", incidentPreference: PER_CONDITION_AND_TARGET}
      ) {
        id
      }
    }
    """)

    policy_template_fmtd = policy_template.substitute({"account_id": account_id})
    nr_response = requests.post(endpoint,
                                headers=headers,
                                json={'query': policy_template_fmtd}).json()

    policy_id = 0
    try:
        policy_id = nr_response['data']['alertsPolicyCreate']['id']
        logger.info(f'   Utilization alert policy successfully created: {policy_id}.')
        return 0
    except KeyError:
        logger.warning(nr_response)

    return policy_id


# TODO: create conditions for CPU and memory, associated with policy ID

def create_conditions(endpoint, headers, account_id, policy_id, logger):
    logger.info('Creating CPU and memory utilization conditions...')
    condition_template = Template("""
    mutation {
      alertsNrqlConditionStaticCreate(
        accountId: $account_id
        policyId: $policy_id
        condition: {
          enabled: true
          name: "$name"
          description: "Alert when $metric utilization is 100% for 5 minutes."
          nrql: {
            query:  "$nrql"
          }
          signal: {
            aggregationWindow: 60
            aggregationDelay: 120
            aggregationMethod: EVENT_FLOW
          }
          terms: [
            {
              operator: EQUALS
              threshold: 100
              priority: CRITICAL
              thresholdDuration: 300
              thresholdOccurrences: ALL
            }
          ]
          violationTimeLimitSeconds: 86400
        }
      ) {
        id
      }
    }
    """)

    conditions = {
        "CPU": {
            "name": "URGENT_CPU_Utilization_100",
            "nrql": "SELECT max(aws.ec2.CPUUtilization) from Metric where metricName = 'aws.ec2.CPUUtilization' facet "
                    "aws.ec2.InstanceId, tags.Name, entityGuid, entityId"
        },
        "memory": {
            "name": "URGENT_Memory_Utilization_100",
            "nrql": "SELECT max(host.memoryUsedPercent) from Metric where metricName = 'host.memoryUsedPercent' facet "
                    "aws.ec2.InstanceId, tags.Name, entityGuid, entityId"
        }
    }

    for key, condition in conditions.items():
        condition_template_fmtd = condition_template.substitute({"account_id": account_id,
                                                                 "metric": key,
                                                                 "name": condition["name"],
                                                                 "nrql": condition["nrql"],
                                                                 "policy_id": policy_id})

        nr_response = requests.post(endpoint,
                                    headers=headers,
                                    json={'query': condition_template_fmtd}).json()

        try:
            condition_id = nr_response['data']['alertsNrqlConditionStaticCreate']['id']
            logger.info(f'   Condition {condition_id} {condition["name"]} successfully created for policy {policy_id}.')
            return 0
        except KeyError:
            logger.warning(nr_response)


# TODO: get Platform workflow; return workflow ID, issuesFilter ID, list of existing associated policies

# TODO: add new policy ID to list of existing workflow policies

# TODO: update Platform workflow with updated list of policies
